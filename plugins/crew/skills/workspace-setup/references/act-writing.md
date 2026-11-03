# Writing the Act: message instructions that read like a person wrote them

Every action that puts words in front of a person needs **message instructions**: `availableActions[].payloadTemplate.prompt`, the "Message instructions" box in the editor. This file covers what to write there, and in `brandVoice`, so the drafts are ones a person would send.

## Contents

- [Why the instructions carry the voice](#why-the-instructions-carry-the-voice)
- [What the writer sees](#what-the-writer-sees)
- [Where each rule goes](#where-each-rule-goes)
- [The shape of good instructions](#the-shape-of-good-instructions)
- [Say each field's format](#say-each-fields-format)
- [Patterns, not sentences](#patterns-not-sentences)
- [Default list of AI tells to ban](#default-list-of-ai-tells-to-ban)
- [Drafts posted for a human (Slack)](#drafts-posted-for-a-human-slack)
- [Name only what exists](#name-only-what-exists)
- [Make facts checkable](#make-facts-checkable)
- [Check the drafts, fix the class](#check-the-drafts-fix-the-class)
- [Worked correction](#worked-correction)

## Why the instructions carry the voice

Three facts about the harness decide this:

1. **No instructions, no message.** For an action with no `payloadTemplate`, content generation is skipped entirely. Turning the agent on only demands instructions for Customer.io, CleverTap, Twilio and Braze, so an empty Slack or webhook box fails silently.
2. **The writer has almost no style guidance of its own.** Its system prompt says, in effect, "you are a content generator, fill these fields as JSON", plus one line of channel tone for some channels (none for Slack or webhook) and the agent's `brandVoice` if set. Left alone, a model writes in its default register: a compliment, a recap, a benefits paragraph, a call request. That is what reads as AI.
3. **The judge (Content check) won't catch it.** It blocks on hard constraints and invented facts. Brand voice is checked only as advisory notes that never change the verdict, and style problems alone are explicitly not a reason to block. There is no second pass that rewrites a weak draft.

So the instructions and `brandVoice` are the only levers. A one-line instruction ("write a partner intro email") gets the model's defaults; a described message gets that message.

## What the writer sees

When it writes, the writer gets:

- **SENDER** — name and title from `availableActions[].sender`.
- **The person** — profile traits and any enrichment facts attached to the agent.
- **Recent events** — the person's session window, with event properties.
- **DECISION CONTEXT** — the action chosen, Decide's rationale, confidence, and each Observe signal's output.
- **Your instructions** — fenced as operator reference material describing what to write.
- **Gathered context** — what the agent's tools found, when it has tools that ran. In Shadow and in a dry run some tools are refused (`agent-schema.md` → "Tools in Shadow and dry runs"), so a draft that needs a public fact should get it from an enrichment.
- **Template structure** — for templated email, where each field lands, so it doesn't repeat itself across fields.

It does **not** see `agentPrompt`, raw tool calls, or anything about the workspace beyond what reached the decision. If the message needs a fact, make sure one of the above carries it.

## Where each rule goes

| Rule                                                                                                   | Put it in                                     | Why                                                                                                      |
| ------------------------------------------------------------------------------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| How every message from this agent sounds: register, words to avoid, sign-off conventions, emoji or not | `brandVoice` (≤2000)                          | Applies to every action, sits at the top of the writer's system prompt, and the judge notes breaks of it |
| What this one message is for, who it's to, its shape, its fields, its length                           | The action's message instructions (≤10,000)   | Per action; an SMS and an internal brief need different shapes                                           |
| How a second or third touch differs from the first                                                     | `followUp.guidance`                           | Only read on follow-ups                                                                                  |
| Facts the message relies on                                                                            | Observe signal outputs and Decide's rationale | The writer sees them, and so does the judge (see below)                                                  |

A rule repeated in `brandVoice` and in every action's instructions is fine; a rule only in `agentPrompt` is lost.

## The shape of good instructions

What worked across real agents, in this order. 400–1,500 characters is typical; length is fine when every line changes the output.

1. **Who, to whom, and why now.** Sender role → recipient role, their relationship (cold, customer, teammate), and the one thing this message must do.
2. **The ideal message, described.** Length, number of sentences or paragraphs, what the opening line does, what the close asks for. Describe it the way you'd brief a sharp new hire.
3. **What to draw on.** Which signal outputs or event facts the message should use, and that it should refer to _the thing_, not the source ("your Lisbon clinic", not "I saw on your website").
4. **Shapes, good and bad.** One sentence-pattern to aim for and one to avoid, written as patterns with placeholders, never with a real customer's names. Concrete entities leak into every draft, and so do whole example sentences ([below](#patterns-not-sentences)); patterns don't.
5. **Avoid list.** The banned phrases and moves (start from the default list below, then add the workspace's own).
6. **Hard limits.** Character or word cap, no invented facts or numbers, no links unless present in the context, no prices, anything regulated.
7. **Fields.** Name each output field, say what goes in it and in what format, because `outputFields` has no descriptions and the writer guesses the format from the name ([below](#say-each-fields-format)).
8. **A closing check.** "Before answering, read it as the recipient. If it could be sent unchanged to someone else, rewrite it."

A template to adapt:

```text
From <sender role> to <recipient role>, who <relationship / how they know us>.
This message has one job: <the single outcome, e.g. get a reply agreeing to a pilot>.

The message: <length cap> words, <n> short paragraphs.
Open with <what the first line does — usually the specific reason for writing, stated plainly>.
Then <the one point about us that matters to them, tied to the signal that triggered this>.
Close with <one concrete, low-effort next step>. Vary the close between drafts.

Use: <signal / event facts to draw on>. Refer to the thing itself, never to where you found it.

Aim for this shape: "<pattern with <placeholders>>"
Not this shape: "<the generic pattern to avoid>"
Write every sentence fresh for this person; none of these patterns is text to copy.

Avoid: <banned list>.
Limits: no facts, numbers or names that are not in the context. No links unless one is in the context. <regulated limits>.

Fields: subject = <what makes a good subject here, length>; body = <the message>; <other field> = <what>.
Format: subject is plain text. body is <n> <p> paragraphs; <other field> is <one <ul> with <n> <li> | plain words, no tags>. Never <the tags you don't want>, links or markdown. (On a plain-text channel: <n> short paragraphs separated by line breaks; no tags, no markdown.)

Before answering, read it as the recipient. If it could go to anyone else unchanged, or sounds like a template, rewrite it.
```

## Say each field's format

The writer decides each field's format before it reads your instructions, and the channel decides it:

- **Plain-text channels: Slack, HeyReach, Twilio and CleverTap.** Every field is plain text, in Shadow too before a channel is picked. A Slack post is mrkdwn and escapes HTML, so a tag shows as text. Ask for line breaks, never tags.
- **Channels whose template supplies the fields** (Customer.io Design Studio, Braze, Twilio Content, a CleverTap campaign's authored keys) set each field's format themselves.
- **Webhook fields you name** (anything but a lone `message`) are plain text values for the receiver's program. The writer is told no HTML, and that a URL is fine when your instructions ask for one, so a profile or deep link copied from a source goes through. HTML tags in these fields are not supported: ask for line breaks, or send HTML through a template channel.
- **A webhook field the receiver cannot do without** goes in `requiredOutputFields` as well as `outputFields` (the editor's Required switch). When the writer leaves it blank, nothing is posted and the decision fails with "<field> had no value; nothing was sent", in Shadow and dry runs too. Without it, a blank `linkedin_url` is posted, the decision reads delivered, and a receiving Agent whose trigger needs the URL never runs. So tell the writer to leave the field empty when the sources do not give it, rather than invent one.
- **A webhook whose only field is `message`, and any channel without fields of its own** (Customer.io or Braze with no template), take the format from the field's name:

| Field name                                                               | What the writer's system prompt says about it                                     |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `subject`, `subject_line`, `preheader`, `preview_text`                   | plain text, no HTML, no links                                                     |
| every other name: `body`, `message`, `headline`, `opening`, `why_now`, … | HTML: "may include inline <a href> anchors, <strong>, <em>, <br>; never markdown" |

So a webhook's lone `message` is an HTML field, and so is a `headline` you meant as plain words on a channel without fields of its own.

**What happened.** An onboarding-email Agent split a HubSpot email template into eight fields. The first dry run put HTML into fields meant as plain words, and "plain text" in the instructions didn't stop it: the instructions ask for one thing and the system prompt for another, and the system prompt wins. What worked was naming the format of every field, in the terms the writer already uses:

- Email sections: "subject and preview_text are plain text. opening is two <p> paragraphs; first_steps is one <ul> with three <li>; headline, proof and cta_label are plain words with no tags. Never <br>, <strong>, <em>, links or markdown."
- A Slack alert: "Write one field, message: two or three short lines separated by line breaks. No HTML tags, no markdown, no links."

That email sent through a webhook, back when every named webhook field was HTML. Its named fields are plain text now, so the `<p>` and `<ul>` sections above need a template channel (Customer.io Design Studio, Braze) to come out as HTML.

Read a draft before assuming either way.

**Links fail the action unless a source gave them.** A field that links to a URL nothing in the decision's context supplied is refused, and the action fails ("links to a URL no source gave this decision"). Never ask for a link the context does not carry.

## Patterns, not sentences

**What happened.** A sales-alert Agent's instructions described the rep's draft note with two example sentences. Twice in one day, drafts came back with those sentences word for word. An example sentence reads to the writer as the answer.

So give the shape with `<placeholders>` where the specifics go, never a sentence that would work as written, and say it outright:

```text
First, one plain sentence, in your own words, about the situation someone in their seat is in: '<what this kind of rollout or job usually turns on>.'
Then an ask with a reason and a size: '<what the call would show them> in <length>.'
Write every sentence fresh for this person; none of these patterns is text to copy.
```

Phrases in an avoid list are fine; they are there to be not written.

Internal labels leak the same way. In one agent, an Observe signal was first named "Digital Twin", and drafts came back with "the twin suggests…" and "twin's FACTS". Name each signal for what it reads ("Who They Are", not "Digital Twin"), and in instructions call it by that name or by what it holds ("what public sources show"). In Crew, "digital twin" means the person's Users page; keep the word out of agents.

## Default list of AI tells to ban

Start every avoid list from this, then add what the workspace's own drafts overuse. These are the patterns readers recognize as generated.

- **Stock openers:** "I came across…", "<Your X> stood out", "I was impressed by…", "I hope this finds you well", "I wanted to reach out", "As a <role>, you…".
- **Reciting them to themselves:** restating the recipient's own website, post, profile or credentials back to them. React to it in one clause; don't summarize it.
- **The product tour:** listing every capability, or a three-benefit triad ("save time, cut costs and scale"). Mention only what the trigger points at.
- **Stock closes:** "Would you be open to a quick / 20-minute call?", "Let me know if you'd like to learn more", "Looking forward to hearing from you", "I'd love to…".
- **Words:** leverage, streamline, seamless, empower, elevate, unlock, robust, cutting-edge, game-changer, delve, excited, thrilled.
- **Constructions:** "not just X, but Y", "whether you're X or Y", a colon before a dramatic reveal, rhetorical questions.
- **Punctuation:** em dashes (use a comma, a full stop or brackets), exclamation marks, emoji unless the brand uses them.
- **Same skeleton every time:** if ten drafts share one structure, the instructions are too prescriptive about order. Describe the job, not the sentence sequence.

Also from experience with outbound: no dates or "recently"; at most one number; no opinions on the recipient's product or strategy, since the sender has no standing to give them.

## Drafts posted for a human (Slack)

A Slack action often carries a draft that a person will send onward: a partner email for the founder to approve, an account brief for an AE. Two things follow:

- **The draft still needs the full instructions.** The Slack channel doesn't check for them and adds no tone line, so this is the case most likely to ship empty or generic.
- **Separate the brief from the draft.** Use separate output fields, for example `subject` and `body` for the draft, plus `why_now` or `qualification_summary` for the reviewer. Write the brief for a busy teammate: verdict first, the evidence in a line or two, no restating of the draft. Write the draft to the bar of the email itself.
- **Say the format.** Slack fields are plain text: ask for line breaks between lines, never tags, which Slack shows as text ([above](#say-each-fields-format)).

## Name only what exists

A message that names the customer's offerings (a plan, a course, a feature, a case study) has to name real ones, described the way the customer describes them. The judge can't catch an invented course: it sees the rationale that named it, and the rationale looks like evidence.

**What happened.** The onboarding email's first course list came from the hero image of an existing email, a designed mock-up. The agent recommended a course the customer doesn't sell, and the user caught it by asking whether the customer has these products at all. The fix had three parts:

1. **A library copied from the live site**: courses, pricing and the product pages, with exact titles, what each is in the customer's words, and what is gated behind a call or a paid plan. It sits in `agentPrompt` as "LIBRARY: the only proof and starting points that exist", with its source and date.
2. **One rule for describing it**: "Describe any offering only as this list does: never claim what it shows, measures or fixes beyond these words."
3. **Decide copies its choices into the rationale**, since the writer can't read `agentPrompt` (oda-design.md → "Decide hands the writer its specifics"), and the message instructions say how each kind of item is used. For a library of workshops plus one hands-on tool: "A workshop is named by its exact title and is something they attend live or watch on demand; never write it as a tool they do a task with. Only <the hands-on tool> is used to do a task. Aim for: 'Join the <workshop title> workshop and bring <one real question from their work>'. Not like: '<a task> with <workshop title>'."

That cut the problem without ending it: graded afterwards, two of three emails still used a workshop as a tool once, one of them in the opening, which the first-steps rule didn't cover. Put a usage rule on every field it applies to, not just the one where it was first caught.

Then check every draft's claims against the library before anyone sees it: after each dry run, list every offering, title and claim a draft names and flag any the library doesn't have. A short script that does this after every run, with the library as its catalogue, keeps it from being skipped.

## Make facts checkable

The judge sees the decision record and the generated content, not the raw event or what research tools returned. A true fact the draft uses but the record doesn't contain reads to the judge as invented, and the draft is blocked. So:

- Have each Observe signal state, in plain sentences, the facts it relied on that the judge can't see elsewhere (the agent's own tool results). Profile enrichments and traits are already in front of the judge. Avoid a `FACTS:` line or `[TAG]` labels: they read as a property dump on the Decisions page (see oda-design.md, "Write readings a person would say").
- Phrase hard constraints in terms the record can show; a constraint the judge can't check causes false blocks.
- Treat a block on a genuinely invented fact as the system working. Fix the evidence, not the judge.

## Check the drafts, fix the class

1. Dry-run the agent (`preview_tryEvent`, or `preview_start` to replay recent decisions once it has some) and read every draft as its recipient.
2. Run a `no-ai-slop` detect pass if available; it names the patterns with quotes.
3. When a draft fails, change the instruction that lets the _whole class_ fail. Never paste the failing draft's entity into the instructions, and never "fix" one case by excluding it.
4. Re-run on cases the change wasn't written against.

## Worked correction

A partner-outreach agent for a scheduling product, Slack-delivered so the founder can review before sending.

**Before** (the instructions as first written):

```text
Draft a partnership intro email to the clinic owner explaining our product and asking for a call.
```

The typical draft from that opens with a compliment on the clinic's "impressive range of services", lists four of them back to the owner, describes five product features, and asks whether they'd "be open to a quick 20-minute call". It is polite, accurate, and obviously generated.

**After:**

```text
From our founder to the owner of a multi-site physiotherapy clinic who has never heard of us.
One job: get a one-line reply saying they'd look at a two-week trial at one site.

The message: under 110 words, three short paragraphs, first person, no greeting beyond "Hi <first name>,".
Open with the operational fact from the signals that makes us relevant (for example, how many sites they run, or that they take online bookings), stated in one plain sentence. No compliment.
Then one sentence on the single thing we do about that fact, with at most one number.
Close by offering the trial at one named site, in a sentence that is easy to say yes to. Do not ask for a call.

Use the clinic facts in the signal outputs. Refer to the clinic and its sites directly, never to "your website".

Aim for: "<fact about their setup>. We <one capability tied to that fact>. <concrete offer they can accept in one reply>."
Not: "I came across <clinic> and was impressed by <list of their services>. We offer <list of features>. Would you be open to a call?"
Write every sentence fresh for this clinic; none of these patterns is text to copy.

Avoid: stock openers and closes, restating their services, feature lists, em dashes, exclamation marks, "excited", "streamline", "seamless".
Limits: no facts, prices or names not in the context. No links.

Fields: subject = under 7 words, names the offer, no punctuation tricks; body = the email; why_now = one line for our founder on why this clinic, today, citing the signal.
Format: subject is plain text. body is three <p> paragraphs. why_now is plain words with no tags. Never <br>, <strong>, <em>, links or markdown.

Before answering, read it as a busy clinic owner. If it could go to any clinic unchanged, rewrite it.
```

The second version doesn't add any facts; it tells the writer what this message is, and what it isn't.
