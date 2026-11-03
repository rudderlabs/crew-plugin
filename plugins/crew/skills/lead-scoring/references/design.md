# Lead-scoring design

What the Agent reads, how it picks a tier, and the facts about Crew that shape both. Read this
before filling `agent-body.json`.

## Contents

- [The shape](#the-shape)
- [Observe: one signal per question](#observe-one-signal-per-question)
- [Decide: one option per tier](#decide-one-option-per-tier)
- [Act: one action per tier](#act-one-action-per-tier)
- [Facts that shape the design](#facts-that-shape-the-design)
- [Writing the tier back to a CRM](#writing-the-tier-back-to-a-crm)

## The shape

A lead score in Crew is a **tier that Decide picks**, backed by separate reads that each say why
in a sentence. Never one composite "overall score" signal: it does Decide's job inside one opaque
prompt and gives the learning loop nothing to tune. Crew grades every signal on one fixed scale
(strong, moderate or weak, with evidence and a confidence), so a signal cannot carry a number or a
custom label. The tier is an Option, because an Option is the one closed choice the decider makes.

A number appears only where a CRM field needs one, mapped from the tier by whoever reads the
webhook (for example Hot = 90, Warm = 60, Cold = 20). The model never invents a number.

## Observe: one signal per question

| Signal (`skillId`)  | Question                            | Where the facts come from                                                                                    | Opening word of the reading                 |
| ------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| `fit`               | Does the company match the ICP?     | The Fit enrichment (cached per person), then company traits, then the email's domain                         | Strong fit, Partial fit, Not a fit, Unknown |
| `role`              | Can this person buy or champion it? | Title, seniority and the role they gave at signup; a LinkedIn research enrichment when there is one          | Decision maker, Champion, User, Unknown     |
| `intent`            | Are they acting like a buyer now?   | Their recent events: pricing, docs, integrations, trial and setup steps, a demo form, and how fast they come | Buying, Evaluating, Browsing                |
| `moment` (optional) | Is there a reason to act now?       | A research enrichment: funding, hiring for the buyer's team, a new leader, a job change                      | Moment, None                                |

Write each `promptFragment` the way `workspace-setup`'s `oda-design.md` says: ask for one to three
plain sentences, opening with the word from the last column, in ONE evidence entry. Name sources in
passing ("they told us at signup", "according to their website"), never field names.

**The ICP goes into the Fit signal itself**: the industries, size, regions and use cases that fit,
and what never fits. Workspace memory does not reach a decision (below), so an ICP written only
there is invisible to the Agent.

**What the lead told you is evidence.** Name in the Fit signal the signup answers that show fit,
such as the tool they are replacing or the products they want. Without the Fit enrichment, a
company nothing describes reads Unknown, and Unknown never reaches Hot.

**Unknown is a real reading.** A free-mail address with no company, or a company the enrichment
could not resolve, is Fit Unknown, not Not a fit. Unknown leads land in Warm, and the nurture asks
for the company.

## Decide: one option per tier

Exactly one tier fits each lead. The rules do not overlap, and Cold is checked first:

| Option (`id`)            | Prefer when                                                                                          | Act       |
| ------------------------ | ---------------------------------------------------------------------------------------------------- | --------- |
| `cold` Cold: record      | Not a fit, whatever the other reads say; or Browsing (no signup, trial or setup step) with no Moment | `record`  |
| `hot` Hot: hand to sales | At least Partial fit and Buying; or Strong fit and a Decision maker who is Evaluating                | `sales`   |
| `warm` Warm: nurture     | Every other lead, including Unknown fit                                                              | `nurture` |

Check the rules for overlap whenever you change them: Hot needs at least Partial fit and Buying or
Evaluating, so it can never meet a Cold lead; Warm is the remainder.

Set `whenNoClearFit` to `closest_action`, so a first-touch lead always gets a tier, and say the
order in `priorityGuidance`.

**Hard constraints** sit above the tiers and end in no action, which is right for people who are
not leads: an existing customer or an open opportunity (name the trait or event that says so), our
own staff and test accounts (for example an `isInternal` trait), and anyone who asked not to be
contacted.

## Act: one action per tier

| Act       | Action                                                                                                                                                               | Channel                |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `sales`   | A Slack post to the sales channel: who, the tier, each reading, and a suggested opener. It goes to a fixed channel, never to the lead.                               | Slack                  |
| `nurture` | A short email, or (when the team works Warm leads on LinkedIn) a webhook that records Warm like Cold; the Warm list for `linkedin-outreach` comes from there.        | Customer.io or webhook |
| `record`  | A webhook that records the tier. It needs no message: the webhook envelope already carries `decisionOutput` with the chosen option, every reading and the rationale. | Webhook                |

The Slack post is the message alone: no action, rationale or signal grade comes with it. So its
message instructions carry everything a seller needs: who
the lead is, the tier and each reading in a line, why now, and an opener they could send, in their
own voice. Write them with `workspace-setup`'s `act-writing.md`.

## Facts that shape the design

Each was checked against how Crew works; recheck before relying on one that matters.

- **Workspace memory never reaches a decision.** Agent creation reads `workspace_md`; the decision
  harness does not. Put the ICP in the Fit signal and the `agentPrompt`.
- **A hold loses the tier.** A decision that takes no action drops its chosen Option,
  and success attribution counts only delivered decisions. So
  Cold must be an action, or Cold leads are neither stored as Cold nor measured.
- **A decision sends at most one action.** One Agent cannot both alert sales and write the tier to
  a CRM. Nothing exports decisions to RudderStack automatically; channel exports carry provider
  callbacks and polled outcomes only.
- **Company facts belong in an enrichment, not in `research_account`.** `research_account` runs only
  at Act time, after the tier is chosen, and the decider never sees it. A profile enrichment is
  prepared before Observe and Decide.
- **Enrichments are per person.** Results are cached per person for the definition's TTL (default
  90 days) and refreshed when their inputs change. Two people at one company are researched twice,
  and nothing rolls several people up into one account score; group calls are dropped.
- **Research values grade "likely" at best.** A research output the evidence does not support is
  dropped, and an "uncertain" value is one the model is told not to rely on. Provider (API or MCP)
  values grade "reported".
- **The default guardrails hold re-scores.** Dedup (72 hours) and the per-person caps (one action a
  day, three a week) would suppress most re-scoring. Turn dedup off and raise the caps.
- **History is short at first.** A person's events are kept 15 minutes until one of them matches a
  trigger, then 15 days, and at most 50 reach the prompt. A short `triggerDelay` (a few minutes)
  lets a burst of signup events land before the decision.
- **Re-scoring needs a new event.** Follow-ups re-run a few times after a first decision, but nothing
  refreshes a cohort on a schedule. Trigger on the events that move intent.
- **Customer.io needs a hosted template, named by `designStudioEmailId`.** On save the server reads
  that template and derives the send id from the transactional message with exactly the same name;
  a bare `transactionalMessageId` is refused at create. Without a template the send is refused, and
  a dry run reports it as failed. The writer then fills the template's `{{trigger.*}}` keys, not
  `subject` and `body`.
- **Webhook payload fields are plain-text strings.** The editor's Payload fields card keeps a webhook
  action's `outputFields` and `requiredOutputFields` across a UI save. A required field left blank
  sends nothing and fails the decision; the envelope's `decisionOutput` does not depend on them.

## Writing the tier back to a CRM

Only the webhook tiers reach it in this design: Cold, and Warm when Warm is worked on LinkedIn. To get every tier into a CRM today, either run a
second Agent on the same triggers whose every option posts to the webhook (twice the decision cost,
untried), or point the one webhook at a receiver that also posts the Slack card (one Agent, a
service to run). The clean fix is an automatic decision export to RudderStack, which does not exist
yet; say so rather than promising write-back.
