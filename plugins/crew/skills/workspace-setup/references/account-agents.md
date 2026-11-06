# Account-level Agents

Crew decides per person. Every decision belongs to one `userId` (or `anonymousId` when there is none). Nothing groups decisions into an account: a workspace with Accounts on groups people into the company they work at (from their email domain, a company trait or, when turned on, `group` calls) and can show an Agent the account's colleagues as context, but a decision is still about one person, and without Accounts there is no account record at all and a `group` call is answered `202 ignored`. An Agent that should decide once per customer account, such as a health score per account or the next onboarding step per new customer, therefore treats the account as the person.

## Contents

- [Start with a dry run](#start-with-a-dry-run)
- [Send one event per account](#send-one-event-per-account)
- [Observe reads the account's facts](#observe-reads-the-accounts-facts)
- [The tier is a Decide Option](#the-tier-is-a-decide-option)
- [Act through a webhook, one action per tier](#act-through-a-webhook-one-action-per-tier)
- [Guardrails count per account](#guardrails-count-per-account)
- [When the people matter too](#when-the-people-matter-too)

## Start with a dry run

The account snapshot event does not exist until a sync sends it, and the session should not wait for one. Write five account snapshots by hand (a healthy account, a falling one, one near renewal, one new and stalled, one with thin data), dry-run the Agent on them in one `preview_tryEvent` call, and agree the tiers with the user. Build the sync after that, with the same property names the dry run used (the `connect-warehouse` skill).

## Send one event per account

- **One track event per account per run**, with `userId` set to the account id and the account's facts as properties: plan, seats, active users this week and last, open support tickets, days to renewal, the onboarding milestones reached and when. A scheduled RudderStack Reverse ETL sync from a warehouse table, or from a RudderStack Profiles table, sends one row per account on a schedule: the `connect-warehouse` skill sets it up. Give the event one fixed name, such as `Account Health Snapshot`. For a tier on every account every run, the sync's mode is Full: Upsert sends only the accounts whose numbers changed, so an unchanged account would keep last week's tier.
- **Prefix the id**, for example `account:<id>`. The id keys the account's event window, its suppression counts and its page under Users, so it must never equal a real person's `userId`.
- **Numbers as numbers, dates as properties.** Send `active_users_7d: 14`, not `"14 users"`. A date goes in a property (`renewal_date: "2027-03-01"`), never onto the event's own timestamp; a timestamp with no time zone is refused with a 400 that a RudderStack Webhook destination does not retry.
- **Roll person events up in the warehouse.** Milestone events from a product's event stream carry a person's id, and Crew cannot join them to an account. Count them per account in the warehouse table the sync reads (`milestones_reached`, `first_data_at`), so the snapshot carries the account's progress.
- **Leave personal contact details off.** An account event needs no email. An action that writes to a webhook or to Slack resolves no recipient; only email, SMS and other messaging channels do, and they belong to a person (below).

## Observe reads the account's facts

Write one signal per aspect of the account, never one "overall health" signal (`oda-design.md` → "Prefer several named signals over one composite"): usage trend, support load, commercial position, onboarding progress. The trigger event's properties are in front of every signal.

Once one of the account's events has matched a trigger, Crew keeps that account's events for 15 days (the default), so a signal can compare today's snapshot with last week's: "Usage falling: active users went from 22 to 9 in two weeks."

A signal's answer has a fixed shape: an `assessment` of `strong`, `moderate` or `weak`, its `evidence` lines and a `confidence`. A signal cannot answer "Red". Write the reading's first word as the plain judgment ("Falling:", "Steady:", "Growing:") and let Decide turn the readings into a tier.

## The tier is a Decide Option

Make each tier an Option (`Green`, `Yellow`, `Red`; or for onboarding `Not started`, `Data flowing`, `Activated`, `Stalled`), each with a `whenToPrefer` that names the signals' readings ("Usage falling and support load high, or renewal within 60 days with usage falling"), and each linked to its own Act.

Every account should get a tier on every run, including the healthy ones, or the downstream table goes stale. So:

- Give the lowest-risk tier a real action too (a webhook that records Green), never "no action".
- Set `decisionLogic.whenNoClearFit` to `closest_action`, so an account that fits no tier cleanly still gets the closest one at low confidence instead of a hold.

## Act through a webhook, one action per tier

The receiving system must read the tier without parsing anything the model wrote. A webhook action does that. The body Crew posts carries:

| Field                                       | Holds                                           | Written by            |
| ------------------------------------------- | ----------------------------------------------- | --------------------- |
| `action`                                    | The chosen action's name, from the Agent body   | Crew, never the model |
| `decisionOutput.nextBestActionId`           | The chosen action's id                          | Crew                  |
| `userId`                                    | The account id the event carried                | Crew                  |
| `decisionId`, `skillId`, `eventName`        | Which decision, which Agent, which trigger      | Crew                  |
| `actionRationale`, `decisionOutput.payload` | Decide's reasons; any fields the action authors | The model             |

So name each tier's action for the tier (`health_red`, `health_yellow`, `health_green`) and key the receiver on `action` and `userId`. Prefer the name to the id: `agent_create` re-mints an action id another Agent in the workspace already uses.

Typical receivers: a small endpoint that upserts `(account id, tier, decided at, decision id)` into a warehouse table, which a Reverse ETL sync then writes to an Account field in the CRM; or a Slack action for the at-risk tier only, to the account team's channel. Upsert by account id, so a repeated tier is harmless.

To send a short reason or a next step with the tier, list them as the action's `payloadTemplate.outputFields` (plain text, one value each) with message instructions that say what each holds (`act-writing.md`). Without message instructions an action generates nothing, which is fine for a webhook that only records the tier.

A Shadow Agent posts nothing. Review its tiers on the Decisions page, or with `analytics_list`, before a person takes it Live; the receiver sees its first call only then.

## Guardrails count per account

Suppression counts this Agent's own delivered decisions for the same `userId`, read from Crew's decisions table, and Live and Shadow are counted apart. A decision that chose no action does not count. The defaults (`guardrails` in the body):

| Rule                         | Default | What it does to a daily snapshot                                                                                   |
| ---------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------ |
| `deduplicationWindow`        | `72h`   | Suppresses two days in three: an account is acted on at most once every 72 hours                                   |
| `maxActionsPerEntityPerDay`  | `1`     | Counts the trailing 24 hours, not the calendar day: a sync that runs a minute earlier than yesterday is suppressed |
| `maxActionsPerEntityPerWeek` | `3`     | Caps a daily tier at three days a week                                                                             |

For a tier that should be refreshed every day, set the dedup window under the sync interval (`20h` for a daily sync), the daily cap to `2` so clock drift cannot suppress a run, and the weekly cap to `7` or more. A suppressed decision is recorded with its reason, so check the first week of decisions for `deduplicated` or `rate_limited` before trusting the receiver's table.

Turn follow-ups off (`followUp: {"enabled": false, "count": 1, "gapDays": 1}`): the next snapshot is the next decision. A body with no `followUp` block is stored with follow-ups on (three, a day apart); in a test account Agent written that way, each snapshot decision would have scheduled three more decisions on the same account before the next sync arrived.

## When the people matter too

An account Agent decides about the account and tells the team. To message the account's people (the power users of a newly onboarded customer, for example), build a person-level Agent instead: each person arrives with their own `userId` and an identify carrying their email, and the account's facts ride on their event as properties (`account_tier`, `account_milestone`). Crew then decides per person, and the guardrails count per person. The two Agents can run side by side on the same events.
