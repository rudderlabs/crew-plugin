# Account-level Agents

An Agent that should decide once per customer account, such as a health tier per account or the next onboarding step per new customer, is built one of two ways. Which one depends on a workspace feature.

- **Account decisions on:** an **account Agent** (`subject: "account"`) decides about the company itself. An **account event rule** tells Crew which events are about an account and where the account's id is. Crew keeps the event's properties as facts on the account, and the Agent's decisions show on the account's page.
- **Account decisions off:** Crew decides per person only, so the account is sent as a person whose user id is `account:<id>`. This is the fallback: [Without account decisions](#without-account-decisions-the-account-as-a-person).

## Contents

- [Which path](#which-path)
- [Design that holds on both paths](#design-that-holds-on-both-paths)
- [The account event rule](#the-account-event-rule)
- [What an account event does](#what-an-account-event-does)
- [The account Agent's body](#the-account-agents-body)
- [Start with a dry run](#start-with-a-dry-run)
- [Act through a webhook, one action per tier](#act-through-a-webhook-one-action-per-tier)
- [Telling the account's owner](#telling-the-accounts-owner)
- [Post once, then only on a change](#post-once-then-only-on-a-change)
- [Guardrails count per account](#guardrails-count-per-account)
- [When the people matter too](#when-the-people-matter-too)
- [Without account decisions: the account as a person](#without-account-decisions-the-account-as-a-person)

## Which path

Account decisions is a workspace feature; [Workspace features](../../../README.md#workspace-features) says whether a new workspace has it and who changes it. It needs Accounts on too. No read tool reports it:

- `accounts_list` answering `ACCOUNTS_OFF` means Accounts is off, so account decisions is off too. Take the fallback.
- Otherwise the first write says. With the user's yes, `agent_create` with `subject: "account"` makes the Agent, Off. If it answers `ACCOUNT_DECISIONS_OFF`, nothing was created: tell the user the feature is off and who to ask (the features table says), and build the fallback now if they want the Agent today.
- `accounts_listEventRules` answers in both cases (an empty list where no rule was ever saved), so it does not tell the two apart.

Never save a rule to find out: create the Agent first. A rule saved for an account-only event changes what that event does, as [the rule section](#the-account-event-rule) says.

## Design that holds on both paths

**One event per account per run**, under one fixed name such as `Account Health Snapshot`, with the account's facts as properties: plan, seats, active users this week and last, open support tickets, the renewal date, the onboarding milestones reached and when. A scheduled RudderStack Reverse ETL sync from a warehouse table, or from a RudderStack Profiles table, sends one row per account: the `connect-warehouse` skill sets it up. For a tier on every account every run, the sync's mode is Full: Upsert sends only the accounts whose numbers changed, so an unchanged account would keep last week's tier.

- **Numbers as numbers, dates as properties.** Send `active_users_7d: 14`, not `"14 users"`. A date goes in a property (`renewal_date: "2027-03-01"`), never onto the event's own timestamp; a timestamp with no time zone is refused with a 400 that a RudderStack Webhook destination does not retry.
- **Dates, not day counts.** Send `renewal_date` and `last_activity_date`, not `days_to_renewal` or `days_since_last_activity`: a count is stale the day after it is computed and changes every row every day. Each fact reaches the Agent with the day Crew recorded it, so tell the Agent in its prompt to take the newest of those days as today and to count days from it, and have the message show the count ("renews 2026-12-29 (41 days)"). In a test on fifteen sample accounts over two rounds, every tier and every day count in a message was right.
- **Roll person events up in the warehouse.** Milestone events from a product's event stream carry a person's id. Count them per account in the table the sync reads (`milestones_reached`, `first_data_at`), so the event carries the account's progress.
- **Leave personal contact details off.** An account event needs no email. An action that writes to a webhook, to Slack or to Salesforce resolves no recipient.

**Observe reads the account's facts.** Write one signal per aspect of the account, never one "overall health" signal (`oda-design.md` → "Prefer several named signals over one composite"): usage trend, support load, commercial position, onboarding progress. A signal's answer has a fixed shape: an `assessment` of `strong`, `moderate` or `weak`, its `evidence` lines and a `confidence`. A signal cannot answer "Red". Write the reading's first word as the plain judgment ("Falling:", "Steady:", "Growing:") and let Decide turn the readings into a tier.

**The tier is a Decide Option.** Make each tier an Option (`Green`, `Yellow`, `Red`; or for onboarding `Not started`, `Data flowing`, `Activated`, `Stalled`), each with a `whenToPrefer` that names the signals' readings ("Usage falling and support load high, or renewal within 60 days with usage falling"), and each linked to its own Act. Every account should get a tier on every run, including the healthy ones, or the downstream table goes stale. So:

- Give the lowest-risk tier a real action too (a webhook that records Green), never "no action".
- Set `decisionLogic.whenNoClearFit` to `closest_action`, so an account that fits no tier cleanly still gets the closest one at low confidence instead of a hold.

## The account event rule

A rule says: an event with this name is about an account, and this is where its id is. `accounts_listEventRules` reads the workspace's rules, `accounts_saveEventRule` creates or replaces one, and `accounts_deleteEventRule` removes one. The two writes need `webhooks:write` (`mcp-map.md` → "Signing in and permissions"). An account Agent only ever receives an event whose name has a rule.

| Field        | Holds                                                                                                                                                                                                                 |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `eventName`  | The event's name, matched exactly, upper and lower case included                                                                                                                                                      |
| `webhookId`  | One webhook's id from `webhooks_list`, or `null` for any webhook. A rule for one webhook beats the any-webhook rule for the same name                                                                                 |
| `about`      | Required. `account`: the event is about the account only. `account_and_person`: it is about both ([When the people matter too](#when-the-people-matter-too))                                                          |
| `keyKind`    | What kind of id the account has, from the table below                                                                                                                                                                 |
| `keyTrait`   | Only with `keyKind: "trait"`: which company id trait                                                                                                                                                                  |
| `keyPath`    | Where the id sits in the event                                                                                                                                                                                        |
| `namePath`   | Optional. Where the account's name sits; used when the event creates the account. Without it a new account is named after its id                                                                                      |
| `domainPath` | Optional, and not with `keyKind: "domain"`. Where the company's domain sits. It links the account to that domain, which can merge an account Crew had formed from the domain alone into this one. It is used only while the workspace groups people by company domain |

**Paths start at the event**, with `properties.` or `context.`: `properties.account_id`. They are the paths `catalog_get` shows for the event. On a custom-format webhook the event's properties are the whole payload the sender posted, so a payload field `account.id` is `properties.account.id`. A rule cannot read the event's user id, anonymous id or message id.

| `keyKind`               | The id is                                                              | Refused when                                                                               |
| ----------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `salesforce.account_id` | A Salesforce account id                                                |                                                                                            |
| `hubspot.company_id`    | A HubSpot company id                                                   |                                                                                            |
| `source`                | The sender's own id for the account (a warehouse's `account_id`)       | `webhookId` is `null`: a sender's own id belongs to one webhook                            |
| `trait`                 | A company id trait, named in `keyTrait`                                | `keyTrait` is not one of the company id traits set in Settings › Accounts                  |
| `group_id`              | The group id RudderStack `group` calls carry                           | Group calls are off in Settings › Accounts                                                 |
| `domain`                | The company's domain                                                   |                                                                                            |

A refused kind answers `ACCOUNT_KEY_KIND_INVALID` with the field in `data.path`. The other refusals name themselves: `ACCOUNT_DECISIONS_OFF`, `ACCOUNT_EVENT_RULE_EXISTS` (this event name already has a rule for this webhook), `ACCOUNT_EVENT_RULE_WEBHOOK_UNKNOWN` (no such webhook in the workspace, or a revoked one) and `ACCOUNT_EVENT_RULE_LIMIT` (the workspace's rule limit). Read the tool's own answer for the rest.

**Ask before saving or deleting a rule, and say what it changes.** Put it to the user in these words, with their event name:

- With `about: "account"`, every event named this (on that webhook, or on every webhook for an any-webhook rule) stops being a person event within about 15 seconds. Crew ignores any user id on it, creates no person from it, and no person Agent runs on it. Run `agent_list` first: a person Agent triggered on that name stops receiving it. Pick a name nothing else sends.
- Saving with an `id` replaces the whole rule: an optional field left out is cleared.
- Deleting a rule makes events of that name person events again. Accounts, their facts and the decisions already made stay.
- A rule stays in force while account decisions is off: its account-only events are then ignored (`202`, `ignored`, reason `account_decisions_off`), never handed to person Agents. Delete the rule to send them to person Agents again.

## What an account event does

An event whose name has a rule, on a webhook of either format:

1. **Finds the account by its id, or creates it.** A `domain` id creates an account only while the workspace groups people by company domain; a free-mail domain or one the workspace excluded never forms an account, and the event is ignored (`unknown_account`).
2. **Stores the event's properties as facts on the account**, each dated when Crew received it. A nested object is flattened (`usage.seats`). The rule's own fields (the id, name and domain) are identifiers, not facts. A property that is a contact detail, an array, a null, an empty string or a very long string is not kept, and neither is one past the per-event or per-account fact limits. The answer lists each one under `skipped` with its path and a reason, and `accounts_get` shows the newest event's list as `lastAccountEventSkipped`. A fact the event stops sending stays.
3. **Queues one decision for each running account Agent triggered on that name.** There is no change check: an unchanged event is decided again, and the Agent's guardrails are what hold a repeat. To keep an Agent from telling the team the same thing on every run, see [Post once, then only on a change](#post-once-then-only-on-a-change).

What the sender sees:

| The event                                                 | Answer                                                                                      |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Accepted                                                  | `202`, `accepted`                                                                           |
| The same message id again                                 | `200`, `duplicate`                                                                          |
| No id at `keyPath` (`account_key_missing`), or a value that is not an id of its kind (`account_key_invalid`), under an account-only rule | `400` on a rudderstack-format webhook, `422` on a custom one. RudderStack shows it as a failed record and does not retry it |
| Account decisions off                                     | `202`, `ignored`, reason `account_decisions_off`                                            |

With `about: "account"` the event needs no user id at all. A Reverse ETL connection still asks for a user identifier column, so the row carries one; Crew does not use it.

## The account Agent's body

`agent_create` with `subject: "account"` (or `draft_createNew`). The subject is set once: a later write that names another subject answers `SKILL_SUBJECT_IMMUTABLE`. Over MCP the Agent starts Off and returns to Shadow, and a person takes it Live in the app, as for any Agent.

`agent_bodySchema` lists the rules an account body must meet. They are checked when the Agent is turned on or published onto, not while it is an Off draft:

- **Slack, webhook and Salesforce actions only.** An account Agent messages nobody at the account. A Salesforce action ("Update Salesforce account") writes fields on the matched Salesforce account and sends no message; `agent_bodySchema` has its rules, and `channels_resources` lists the Writable fields it may use. Needs the Salesforce account writes feature ([Workspace features](../../../README.md#workspace-features)); nothing is written until a person takes the Agent Live in the app. A Slack destination is a channel or the account's owner ([Telling the account's owner](#telling-the-accounts-owner)), never a person at the account.
- **No follow-ups, no trigger delay.** Write `followUp: {"enabled": false, "count": 1, "gapDays": 1}` and `scheduling.triggerDelay: "0s"`. The next event is the next decision.
- **No `accountContext` and no per-action `account` limits.** Both belong to a person Agent; an account Agent always sees its account.
- **Tools and enrichments.** `agentToolNames` may name any tool but `identify_visitor_company`. `enrichmentIds` may name only enrichments whose subject is `account`.
- **Triggers** are event names that have a rule. The body is accepted with a name that has none yet, so the Agent can be built before the rule or the first event exists; until the rule is saved, events of that name are person events and never reach it.
- `successEvent`, `guardrails` and `needsApproval` work as for a person Agent. A success event is an account event too, so its name needs a rule.

**What Decide sees.** The account's current facts; each fact's earlier values with when each was observed, so a signal can say "active users went from 22 to 9 in two weeks"; the account's people by name and role with the names and times of their recent events, never an email, a phone number or an id; and this Agent's own earlier decisions about the account, the ones that chose no action included. Each decision records what was missing when it was made: `no_people` when nobody is linked to the account, `history_unavailable` or `history_behind` when the earlier values could not be read. The Agent still decides.

## Start with a dry run

`preview_tryEvent` on an account Agent takes the account's `accountId` (from `accounts_list`), the `eventName` and its `properties`, and no person field. The account has to exist in Crew: one Crew does not have answers `NOT_FOUND`. The answer carries an `accountSnapshot`: the facts, their earlier values, the people count and the gaps Decide saw. Nothing is sent and no decision is written. The account's stored facts stay in the snapshot beside the properties the dry run passes, so a column the model has since dropped is still there: to test a changed set of columns, dry-run on an account that never held the old ones.

- **Where Accounts already holds companies**, pick five from `accounts_list` (a healthy one, a falling one, one near renewal, one new and stalled, one with thin data), write each one's properties by hand, and dry-run them in one `preview_tryEvent` call. Agree the tiers with the user, then build the sync with the same property names (the `connect-warehouse` skill).
- **Where no account exists yet**, the first events create them. Save the rule, keep the Agent Off, and send one row (`connect-warehouse` step 7): the account appears in `accounts_list` with its facts, and no decision is made. Dry-run on that account, then move the Agent to Shadow with the user's yes.

`accounts_list` and `accounts_get` need `users:read`. Calibrate works for an account Agent once it has decided about accounts in Shadow: its cards are its past account decisions.

## Act through a webhook, one action per tier

The receiving system must read the tier without parsing anything the model wrote. A webhook action does that. The body Crew posts for an account Agent carries:

| Field                                       | Holds                                                                            | Written by            |
| ------------------------------------------- | -------------------------------------------------------------------------------- | --------------------- |
| `action`                                    | The chosen action's name, from the Agent body                                    | Crew, never the model |
| `subject`                                   | `"account"`                                                                      | Crew                  |
| `account.id`, `account.name`                | Crew's id for the account, and its name                                          | Crew                  |
| `account.key`                               | `{kind, value}`: the id the event named, so the receiver can find its own record | Crew                  |
| `decisionId`, `skillId`, `eventName`        | Which decision, which Agent, which trigger                                       | Crew                  |
| `actionRationale`, `decisionOutput.payload` | Decide's reasons; any fields the action authors                                  | The model             |

It carries no `userId` and no `anonymousId`. Name each tier's action for the tier (`health_red`, `health_yellow`, `health_green`) and key the receiver on `action` and `account.key.value`. Prefer the action's name to its id: `agent_create` re-mints an action id another Agent in the workspace already uses. For a `source` rule `account.key.kind` reads `source:<webhook id>`, and for a `trait` rule `trait:<name>`.

Typical receivers: a small endpoint that upserts `(account id, tier, decided at, decision id)` into a warehouse table, which a Reverse ETL sync then writes to an Account field in the CRM; or a Slack action for the at-risk tier only, to the account team's channel. Upsert by account id, so a repeated tier is harmless.

To send a short reason or a next step with the tier, list them as the action's `payloadTemplate.outputFields` (plain text, one value each) with message instructions that say what each holds (`act-writing.md`). Without message instructions an action generates nothing, which is fine for a webhook that only records the tier.

A Shadow Agent posts nothing. Review its tiers on the account's page or the Decisions page, or with `analytics_list` (`subject: "account"`), before a person takes it Live; the receiver sees its first call only then.

## Telling the account's owner

"Tell the account manager when one turns Red" needs the owner on the account, and then one of two ways to reach them. This section is read from `agent_bodySchema` and the rule tool's own description; it has not been run in a test here.

- **The owner comes from the rule.** `accounts_saveEventRule` takes an `ownerPath`: the property that holds the account's owner, as an email address or a Slack member id (`properties.owner_email`). Crew stores it on the account and leaves that property out of the facts. A later event with a different owner replaces it; an event without one keeps it. Send the owner as a column of its own, and keep the owner's name in another column if the message should show it.
- **Mention the owner in a channel post.** `tagAccountOwner: true` on the Slack action's policy: a Live post starts with a mention of the owner. With no owner stored, or one Slack cannot find, the post goes out untagged.
- **Or message the owner directly.** A Slack action whose `destinationId` is `crew:slack:account-owner` sends a direct message in place of a channel post. It fails when the account has no owner yet, and a person cannot take the Agent Live until the Slack app can look people up by email (`agent_bodySchema` names the refusal).

## Post once, then only on a change

A Full sync sends every account on every run, so an Agent that alerts on a Red account would alert on it again each time. Guardrails can only space the repeats out. Decide sees this Agent's own earlier decisions about the account, so the Agent can hold the repeat itself:

- **Give it one quiet action for "nothing new"**, a webhook action such as `no_change_recorded` whose one field says the tier, when it was set and that the facts behind it have not moved. It is a real action, so the decision is recorded and the receiver's table stays current.
- **Say when to choose it, in Decide.** "Check this account's earlier decisions first. If the last one had the same tier and the facts behind it have not moved, choose No change, whatever the tier. Decide afresh when the tier would change, on the run where the renewal first comes inside 90 days, or when a fact behind the call moved by a real amount, such as active users by a tenth or more, a new ticket or a new note. A date coming one day closer is not a change. With no earlier decision, decide as if it were the first time."

In a test on fifteen sample accounts, a second run with the same facts chose No change for all fifteen over two rounds, and a run where four accounts' facts moved decided those four afresh. Without the rule an Agent written as one Decide strategy avoided repeating itself by calling an already-flagged account healthy, which is wrong: give it the quiet action.

Three things to plan for. A receiver that writes the tier from the action's name keeps the tier it has when this action arrives. Decide lists only the Agent's recent decisions about the account (ten of them, from the last thirty days, by default), so have the quiet action's field restate the tier, which is what carries it from one run to the next. And two cases were not tested: the fallback path, and the first run after a person takes the Agent Live, when every earlier decision is a Shadow one that told nobody. Read that run's decisions; if it held alerts back, add to the rule that a decision made in Shadow posted nothing.

A dry run on an account that already has a decision follows the same rule, so it can answer No change. To see a first-time call, dry-run on an account with no decisions yet.

## Guardrails count per account

Suppression counts this Agent's own delivered decisions for the same account (on the fallback path, the same `userId`), and Live and Shadow are counted apart. A decision that chose no action does not count. The defaults (`guardrails` in the body):

| Rule                         | Default | What it does to a daily snapshot                                                                                   |
| ---------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------ |
| `deduplicationWindow`        | `72h`   | Suppresses two days in three: an account is acted on at most once every 72 hours                                   |
| `maxActionsPerEntityPerDay`  | `1`     | Counts the trailing 24 hours, not the calendar day: a sync that runs a minute earlier than yesterday is suppressed |
| `maxActionsPerEntityPerWeek` | `3`     | Caps a daily tier at three days a week                                                                             |

For a tier that should be refreshed every day, set the dedup window under the sync interval (`20h` for a daily sync), the daily cap to `2` so clock drift cannot suppress a run, and the weekly cap to `7` or more. A suppressed decision is recorded with its reason, so check the first week of decisions for `deduplicated` or `rate_limited` before trusting the receiver's table.

Turn follow-ups off (`followUp: {"enabled": false, "count": 1, "gapDays": 1}`): the next snapshot is the next decision. An account Agent with follow-ups on is refused when it is turned on. On the fallback path nothing refuses it: a body with no `followUp` block is stored with follow-ups on (three, a day apart), and in a test Agent written that way each snapshot decision would have scheduled three more decisions on the same account before the next sync arrived.

## When the people matter too

An account Agent decides about the account and tells the team. It messages nobody at the account. To message the account's people (the power users of a newly onboarded customer, for example), build a person Agent beside it.

**With account decisions on**, one event can reach both. A rule with `about: "account_and_person"` treats the event as a person event and an account event at once:

- The event is an ordinary person event, so it carries the person's own user id (and an email, for an Agent that emails them). Person Agents triggered on its name decide about the person, as they would with no rule.
- Account Agents triggered on the same name decide about the account, and the event's properties become the account's facts.
- The person joins the rule's account on that event. They need not carry the account id as a trait.
- Each kind of Agent decides once, and their guardrails count apart: per person, and per account.
- An event with no usable account id is still a person event: the person Agents run, and the answer's `account` field says the account half was skipped (`account_key_missing` or `account_key_invalid`). With account decisions off the person Agents run too, and `account` reads `ignored`.

Use it for an event that is about one person at a company (a seat added, a trial started by a named user). A snapshot row per account names no person: keep that rule `about: "account"`, and reach the people through their own events, with the account's facts on them as properties (`account_tier`, `account_milestone`) or as traits (`connect-warehouse` → pattern 4).

**With account decisions off**, build a person-level Agent instead: each person arrives with their own `userId` and an identify carrying their email, and the account's facts ride on their event as properties. Crew then decides per person, and the guardrails count per person. It can run beside the account-as-a-person Agent below on its own events.

## Without account decisions: the account as a person

The fallback, for a workspace where account decisions is off. Crew then decides per person only: every decision belongs to one `userId` (or `anonymousId` when there is none). A workspace with Accounts on groups people into the company they work at and can show a person Agent the account's colleagues as context, but a decision is still about one person. So the Agent treats the account as the person. Tell the user this is the fallback, and that the Agent is rebuilt as an account Agent once the feature is on: an Agent's subject cannot change.

Everything under [Design that holds on both paths](#design-that-holds-on-both-paths), [Act through a webhook](#act-through-a-webhook-one-action-per-tier) and [Guardrails count per account](#guardrails-count-per-account) applies, with these differences:

- **No rule, and an ordinary Agent.** `agent_create` with no `subject`. Save no account event rule for the event's name.
- **`userId` is the account id, with a prefix:** `account:<id>`. The id keys the account's event window, its suppression counts and its page under Users, so it must never equal a real person's `userId`. Nothing groups these decisions into an account record.
- **Dry-run with no events and no account.** Write five account snapshots by hand, each with a made-up `userId` of `account:<id>`, and run them in one `preview_tryEvent` call.
- **History is the event window.** Once one of the account's events has matched a trigger, Crew keeps that `userId`'s events for 15 days (the default), so a signal can compare today's snapshot with last week's.
- **The webhook body carries `userId`**, the prefixed account id, in place of `subject` and `account`. Key the receiver on `action` and `userId`.
- **Review** a Shadow Agent's tiers on the Decisions page or with `analytics_list`.
