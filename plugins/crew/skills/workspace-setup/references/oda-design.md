# ODA design: what belongs in which layer

Most bad agent designs are not bad _content_ — they're content in the wrong layer. Signals doing Decide's job, cadence encoded as a signal, lookups dressed up as judgments. The result reasons poorly and can't be tuned.

Read this before writing any agent content.

## Contents

- [The three layers](#the-three-layers)
- [Observe: what earns a signal](#observe-what-earns-a-signal)
- [Write readings a person would say](#write-readings-a-person-would-say)
- [Prefer several named signals over one composite](#prefer-several-named-signals-over-one-composite)
- [Decide: constraints and options](#decide-constraints-and-options)
- [Act: actions and cadence](#act-actions-and-cadence)
- [Timing](#timing)
- [Shadow mode](#shadow-mode)
- [Worked correction](#worked-correction)

## The three layers

| Layer       | Answers                         | Contains                                         |
| ----------- | ------------------------------- | ------------------------------------------------ |
| **Observe** | What's true about this entity?  | Signals producing graded reads over the data     |
| **Decide**  | Given that, what should happen? | Hard constraints, options, preference conditions |
| **Act**     | How does it happen?             | Actions, channels, message generation, cadence   |

Every decision is about one entity: one `userId`. For an Agent that decides per customer account (a health tier, the next onboarding step for a new customer), the account is that entity, and its tier is a Decide Option, not a signal: `account-agents.md`.

## Observe: what earns a signal

A signal should be a **graded judgment over data the agent would otherwise not synthesize**. Three tests — failing any one means it isn't a signal:

1. **Is it a judgment, not a lookup?** Facts arriving on the trigger payload — timestamps, IDs, assigned owner, stage — are already visible. A signal that restates them adds nothing.
2. **Is it separable?** If it can't vary independently of another signal, it isn't a distinct signal.
3. **Does it change the decision?** If every possible output leads to the same option, it's decoration.

Common false signals:

- **Payload restatement.** "Summarize the booking details." The agent already has them.
- **Reachability and consent.** Whether you're _permitted and able_ to contact someone is a hard constraint — a kill switch — not a graded signal. Constraints belong in Decide.
- **Fixed-channel selection.** If the channel is settled by the use case, "which channel?" isn't a decision.
- **Cadence.** "How many touches fit before the deadline" is Act-layer scheduling. It lives in the follow-up configuration.

What genuinely earns a signal: **behavioral history and trajectory** — things that require looking across events over time and forming a graded read. Momentum (warming or cooling), reliability (track record), quality grading (which cohort this entity resembles).

## Write readings a person would say

A signal's reading is what an operator and a prospect read on the Decisions page, so it should sound like judgment, not like a record. Readings formatted as `WHO: … [TOLD] / FACTS: …` or as CAPS codes (`TEAM_BUYER — …`) were called "a bad experience" by the people reviewing an onboarding-email Agent; rewriting them as plain language fixed it. In each signal's `promptFragment`:

- Ask for one to three plain sentences, and end with "Put the whole reading in ONE evidence entry, as a single paragraph, not one entry per sentence." The UI renders each evidence entry as a bullet.
- A graded signal opens with a plain word or phrase ("Team buyer:", "Not an MQL:", "Expert:"), then says why. Refer to those words in priority guidance, options and hard constraints ("when Buying For says Covered…").
- Name sources in passing ("according to LinkedIn", "they told us"), never as tags, and forbid internal field and tool names (enrichment, employee_band…).
- Ask for the decision rationale as two to four plain sentences. If the writer must reuse exact facts (a proof point, a call-to-action key), end the rationale with one natural sentence that names them ("For proof, use … The call to action is book_call.").
- Name each signal for what it reads, never with a product term ("Who They Are", not "Digital Twin").

Renaming a signal does not rename the readings on past decisions, so settle names before the first decisions you want to keep.

## Prefer several named signals over one composite

A single composite signal — "assess overall risk" — is tempting and usually wrong. Two reasons:

**It does Decide's job.** Weighing factors against each other _is_ the decision. Pushing it into one Observe signal hides the reasoning inside one opaque prompt.

**It gives a learning loop nothing to hold.** Improvement works by changing one thing at a time — add a signal, drop a signal, reweight a signal, then measure. Three named signals expose three tuning surfaces. One composite exposes a prompt you can only rewrite wholesale, with no way to attribute the change.

So: decompose into independently-named signals, and let Decide synthesize them. Then reference the signals explicitly in the options' preference conditions, so the synthesis is visible rather than implied.

## Decide: constraints and options

**Hard constraints** are non-negotiable suppressions evaluated independently of judgment: missing consent, missing contact details, entity in a terminal state, compliance holds. Each pairs a condition with an effect. They're not preferences and they don't get weighed.

**Options** are the choices available. Each needs:

- A **stable identifier** and a human-readable **name**.
- A **preference condition** — when to choose this over the others. Reference the Observe signals by name.
- A **link to an act** (`actId`), and that act must own at least one action.

Design them to be **collectively exhaustive and mutually distinguishable** across the situations where acting is right. **Silence is built in; don't build an option for it.** The Decide model can always choose `no_action`, and it must when a hard constraint fires. `decisionLogic.whenNoClearFit` sets what happens when no option clearly fits: `hold_off` (the default, and usually right for anything reaching a real person) means a weak or partial fit holds; `closest_action` means the agent always acts unless a hard constraint fires. A "do nothing" option can't be expressed anyway — every option must link to an act that owns an action. Put the reasons to hold in hard constraints and `priorityGuidance`, so each hold names its reason.

**Decide hands the writer its specifics.** The writer never sees `agentPrompt`, so a library that lives there (offerings, case studies, starting points) reaches the message only through Decide's rationale. Have Decide end its rationale with one sentence naming what it chose, copied exactly from the library: "For proof, use <story>. Start them with <starting point> and <starting point>. The call to action is <key>." The writer and the judge then see the same items. Choose what to hand over with the message in mind: the writer uses each item the way its name suggests, so when an onboarding-email Agent named two workshops as starting points, the drafts wrote them as tools ("Map one customer-call workflow with <workshop title>"). The fix was in Decide: always the one starting point a person does a task with, plus one more (act-writing.md → "Name only what exists").

Preference conditions should describe _the situation_, not restate the option name. "High risk from falling momentum or an at-risk history, reachable, and enough time remaining" is usable. "When high-risk sequence is appropriate" is circular.

## Act: actions and cadence

Actions carry the channel and the message generation. **Every action that produces words for a person needs message instructions** (`availableActions[].payloadTemplate.prompt`); an action without them decides and then generates nothing. The instructions cover:

- **Who it's from and to**, and the relationship.
- **The one thing the message should accomplish.**
- **The ideal message, described**, with the shapes to aim for and avoid.
- **Hard content limits** — length, and prohibited content. In regulated contexts be explicit and exhaustive here.

Voice that applies to every action goes in the agent's `brandVoice`. The harness adds almost no style of its own and the judge doesn't block on style, so these two fields decide whether drafts read as written by a person. `act-writing.md` has the shape, a default list of AI tells to ban, and a worked correction.

**Cadence belongs in the follow-up configuration**, not in a signal and not in the action prompt: how many touches, the gap between them, the window they must fit inside. Match the window to the real-world window the use case operates in.

**Consider fixed templates over generated copy in regulated contexts.** A locked template with merge fields gets compliance sign-off once; generated copy needs review every time. The agentic value is usually in _which_ action and _whether_ to act — the risk read — rather than in novel copy per send. Raise this as a choice rather than deciding it silently.

## Timing

**Default to no delay after the trigger.** If the decision window is short, a delay consumes the window the agent exists to act within, and the first touch is most effective while intent is fresh.

**The exception: facts that land just after the trigger.** A signup is often followed within a minute or two by the onboarding answers or a quiz, and a decision made at the trigger misses them. A short debounce fixes that: `scheduling.triggerDelay` (for example `"2m"`) holds the decision, and a repeat trigger for the same person pushes it back. Keep it well under 15 minutes. Events kept under an anonymous id that has not itself matched a trigger, such as a website quiz when the trigger comes from the backend, are dropped after 15 minutes.

Spacing lives in the follow-up configuration. Note the edge case: fixed day-based gaps don't fit windows measured in hours. When the use case spans both — some entities acting days ahead, some hours ahead — flag whether window-relative spacing is supported. It's a real gap worth naming rather than papering over.

## Shadow mode

Shadow means **the agent decides but never delivers**. It is one of the agent's three runtime states (Off, Shadow, Live), set on the agent rather than per action; every decision and its generated draft is recorded and visible on the Decisions page, but no send happens. See `agent-schema.md` for how to move between states.

Shadow also refuses any tool it can't classify as a read, so a Shadow agent can decide on less than the same agent would Live. Since Shadow is where a team decides whether to go Live, check that its tools ran (`agent-schema.md` → "Tools in Shadow and dry runs").

Two things follow, and both are worth saying explicitly to everyone who reads the results:

A Shadow agent needs no connected channel: each action may name only a `channelType` (`slack`, `webhook`, `customerio`, ...), and the drafts are written in that channel's voice. Going Live needs a real channel id on every action, so channels are connected in the app before that step, not before Shadow.

**Shadow is a 100% holdout.** Nothing is delivered, so delivery rates, response rates, and lift are structurally inapplicable — not missing data. Showing them as zero misrepresents the mode.

**So define the shadow-mode metric as the baseline outcome rate of the entities the agent targeted.** That's what makes later lift computation possible, and it's measurable while nothing sends.

Shadow is also the answer to compliance objections: decisions are drafted for human review, and nothing reaches anyone until the team is satisfied. Say that plainly: in a regulated business it is usually what makes starting possible.

## Worked correction

A first-draft Observe layer for a no-show reduction agent:

- ~~Channel Responsiveness~~ — "confirm contact details and consent are on file; pick a channel." Consent and contactability are **hard constraints**; the channel was fixed by the use case. The one genuine signal buried inside — whether this entity responds on that channel — belongs folded into a behavioral signal.
- ~~Booking Context~~ — "summarize datetime, owner, and how many touches fit." The facts arrive on the payload; the touch count is **follow-up configuration**.
- ~~Overall No-Show Risk~~ — a single composite. Does Decide's job and gives the learning loop nothing to tune.

Corrected:

- **Engagement Momentum** — rising, flat, or falling, from post-trigger engagement across email and web.
- **Booking Reliability** — reliable, unproven, or at-risk, from prior no-shows and reschedules.
- **Lead Intent Quality** — high, medium, or low, from acquisition path.

Each is a graded judgment over behavioral history, independently variable, and independently tunable. Decide weighs them; the options name them in their preference conditions.
