---
name: lead-scoring
description: Build a lead-scoring Agent in RudderCrew (Crew) that reads each lead's fit, role and intent separately, picks a tier (Hot, Warm or Cold) with its reasons, and routes it - Hot to sales in Slack, Warm to nurture, Cold recorded - then dry-runs it, runs it in Shadow and measures it against outcomes. Use when someone wants to score, qualify, prioritise or route leads, signups or trial users with Crew; asks which signups sales should call first; wants MQL, PQL, ICP-fit or predictive lead scoring; or wants inbound leads tiered and handed to sales. Trigger even when the user names only the company ("set up lead scoring for Acme") without saying Crew.
compatibility: The Crew MCP connected to the user's workspace; the workspace-setup skill in the same plugin (schema, message writing, check_body.py). The optional Fit enrichment needs the workspace's Profile enrichment feature (on by default; the Agent works without it), the built-in web tools (on by default), and users:read on the Crew MCP (the user's role over the OAuth sign-in, or a token with the people scope).
---

# Lead scoring with Crew

This skill builds one Crew Agent that gives every new lead a tier with its reasons and routes it:

```text
Observe                Decide                       Act
Fit    (company)  ┐                               ┌ Hot   → Slack card to sales
Role   (person)   ├─▶  one tier per lead,  ───────┼ Warm  → nurture email
Intent (behaviour)┘    Cold checked first         └ Cold  → webhook records the tier
```

A lead score in Crew is a **tier that Decide picks**, backed by separate reads, never one composite
"score" signal. `references/design.md` explains the shape and the facts about Crew behind it; read
it before writing the body. Two facts change most first drafts:

- **Workspace memory never reaches a decision.** Write the ICP into the Fit signal and the
  `agentPrompt`, not only into workspace memory.
- **Cold must be an action, not a hold.** A decision that takes no action loses its tier and is
  never measured, so Cold posts to a webhook.

This skill builds on `workspace-setup` (the body schema, message writing, `check_body.py`). Read
its `references/agent-schema.md` and `references/act-writing.md` when this skill points at them.

## Only a human can do these

Ask the user; never work around them.

- Create channels (a sales Slack channel, a webhook for Cold, Customer.io for nurture). The MCP
  lists channels but cannot create them.
- Get Profile enrichment turned back on, if the Fit enrichment is wanted and this workspace has it
  switched off (step 3 shows how to tell). It is on by default; only the RudderStack team can turn it
  back on. Don't wait for it: build without Fit research and add it later.
- Agree the gate's pass thresholds (`references/measuring.md`).
- Switch the Agent Live.

## 1. Collect the inputs

Ask for what you cannot read from the workspace:

1. **The ICP.** Industries, company size, regions and use cases that fit; the buyer and champion
   roles; who never fits. Take the team's own words. Where they have a scoring sheet or a CRM rule,
   read it for the ICP, but keep its score out of the Agent (`measuring.md`).
2. **What sales gets.** The Slack channel for Hot leads, and what a seller needs to see.
3. **What Warm gets.** A nurture email, or, when the team works Warm leads on LinkedIn, a webhook
   that records Warm the way Cold is recorded (the Warm list for `linkedin-outreach` comes from
   there). Never leave Warm with no action: an Option's Act must own one, and a no-action decision
   drops its tier. The email needs a bound Customer.io channel, a sender, and a Design Studio email
   for `designStudioEmailId`. On create the server reads that template and takes the send id from
   the Customer.io transactional message with exactly the same name, so that message must exist
   first. Never send a bare `transactionalMessageId`: create refuses it.
4. **The outcome.** The event that says a lead converted, such as a booked meeting or a created
   opportunity.
5. **Who is not a lead.** The trait or event that marks an existing customer or open opportunity,
   and the one that marks staff or test accounts.

## 2. Read the workspace

- `context_get`: the business in the team's words. It feeds Agent creation, not decisions; copy
  what the Agent needs into the body.
- `catalog_list`, then `catalog_get` on every event you might use. Triggers and every property path
  you write must come from here: an invented event name gates the Agent out of every decision.
  Pick:
  - the **trigger events**: the signup or lead event, and one or two events that move intent
    (pricing, a demo form, a real setup step);
  - the **success event** from step 1;
  - the **traits** Fit and Role read (company, email, title, the role given at signup), and the
    customer and internal markers for the hard constraints.
- `channels_list`: the Slack, webhook and Customer.io channel ids. Shadow runs on `channelType`
  alone; Live needs a `channelId` on every action.

## 3. The Fit enrichment (recommended)

Company facts belong in a profile enrichment, which is prepared before the Agent decides. Without
one, Fit reads only the traits and the email's domain, and most leads come out Unknown.

The enrichment needs two workspace features. **Profile enrichment** is on by default; if someone
switched it off, the RudderStack team turns it back on. The **built-in web tools** (`web_search`,
`web_fetch`), which the template researches with, are on unless someone turned them off. When both
are on, this step just works.

1. Fill `references/fit-enrichment.json`: the ICP in the brief, the industry options.
2. `enrichment_preview` with two real leads (a strong fit and a weak one) and show the user the
   results. An empty result for a free-mail lead is correct.
3. `enrichment_create`, and keep the id for `enrichmentIds`.

The preview in 2 tells you what the workspace has:

- `FORBIDDEN` "Profile enrichment is not enabled for this workspace": the feature was switched off.
- `BAD_REQUEST` "A source is missing, disabled, or unavailable in this workspace": the web tools are
  off.
- `FORBIDDEN` "Missing permission: users:read": the caller can't read people. Over the OAuth sign-in
  that is the user's role; on a personal access token, the `people` scope.

On any of these, skip this step and build the Agent without `enrichmentIds`: Fit then reads the
traits and the email's domain. Tell the user what to ask for (the RudderStack team enables the two
features; a workspace admin changes a role), and come back to this step once it is in place.
A Role research enrichment (title and seniority from LinkedIn) and a Moment enrichment
(funding, hiring, a new leader) follow the same pattern; add a `moment` signal and mention Moment
in the Cold option when you add the latter.

## 4. Write the body

Start from `references/agent-body.json` and replace every `<placeholder>`:

- The ICP goes into the Fit `promptFragment` and the `agentPrompt`, the buyer roles into Role, and
  the buying events into Intent. Keep each reading's opening words as they are: the options refer
  to them.
- Name, in the Fit signal, the signup answers that show fit (the tool they are replacing, the
  products they want). Without the Fit enrichment a company nothing describes reads Unknown, and
  Unknown never reaches Hot: in the first dry run, a head of data replacing Segment on the pricing
  page landed in Warm until her own signup answer counted as evidence.
- Keep the three options and their rules. If you change a rule, check that no lead can meet two
  options and that Cold still comes first (`design.md`).
- Triggers and the success event come from step 2. Keep the `triggerDelay` of a few minutes, so a
  burst of signup events lands before the decision.
- Keep dedup off and the caps raised: the defaults would hold most re-scores.
- Write the Hot card's and the nurture email's message instructions with `workspace-setup`'s
  `act-writing.md`. With a Customer.io template the writer fills the template's `{{trigger.*}}`
  keys (`subject` and `body` are only the fallback), so name each of those keys. The Cold webhook
  needs none.
- Keep `launchMode: "shadow"`. The server creates an MCP-made Agent Off and turns it on in Shadow
  anyway; the body should say what it will run as.

Run `workspace-setup`'s `scripts/check_body.py` on the body and fix every ERROR. Expect one WARN
for the Cold webhook having no message instructions; that one is correct.

## 5. Create it and dry-run it

1. `agent_create` with the body, then `agent_get` and compare what came back with what you sent.
2. One `preview_tryEvent` call, with a list of five events, on the signup trigger for five made-up leads, with traits and properties at
   the paths `catalog_get` showed, and a fresh `userId` each:
   - a decision maker at a strong-fit company;
   - someone at a partial-fit company who has just viewed pricing;
   - a student or a free-mail address with no company;
   - a strong-fit company but a reader who is only browsing;
   - one of your own staff (the internal marker set).
3. Run each lead twice. A reading may wobble between runs (Strong fit once, Partial fit the next);
   the tier should not. When a tier flips, tighten the rule or the reading that decided it.
4. Show the user a table: lead, tier, the three readings, and what the action would have said.
   Check:
   - each lead lands in the tier the rules give;
   - Cold comes back as the webhook action, not as no action;
   - the staff account is held by its hard constraint;
   - the Hot card names facts the lead's data supports, and nothing about tracking or scores.

A dry run enriches a real person who has no current result, as Live does; a made-up `userId` has
nothing to enrich. So give each made-up lead the company facts the Fit signal reads (company, size,
the signup answers) in its traits or properties, or Fit reads Unknown and no one reaches Hot. Or
dry-run real leads by their `userId` from `users_list`. **Stop here until the user approves the
readings and the card.**

## 6. Shadow and the gate

1. Tell the user how often the trigger fires (its `seenCount` between `firstSeen` and `lastSeen` in
   `catalog_list`, or a day of `get_source_event_metrics` on the RudderStack MCP) and that in Shadow
   each match is one model decision, recorded on the Decisions page and sending nothing. On a busy
   trigger, narrow it with a `when` condition first. With their yes, `agent_update` to `shadow`.
2. Agree the gate with the user before real leads accumulate: cohort, outcome window, baseline,
   pass thresholds, Cold review and approver (`references/measuring.md`).
3. Read the decisions as they come in (`analytics_list` with every outcome, then `analytics_get`),
   watch the tier mix, and fix one signal or option at a time.

## 7. Hand Live to a human

When the gate passes, tell the user to switch the Agent Live in the Crew UI, after binding a real
`channelId` on every action. Consider `needsApproval` on the Hot action for the first week.

## What this play does not do yet

Say these plainly when they come up; they are product gaps, not things to work around:

- **Writing every tier to a CRM.** A decision sends at most one action, and Crew has no automatic
  decision export. Only the tiers routed to a webhook reach it: Cold, and Warm when Warm is worked
  on LinkedIn (`design.md`, last section).
- **Account scores.** Every read is per person; nothing combines several people at one company.
- **Scheduled re-scoring.** A lead is re-scored when a trigger event arrives, not on a timer.
