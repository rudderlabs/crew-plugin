# The workspace context doc

The context doc tells Crew's Agent builder — and any human reading the workspace — who this organization is, what they're trying to move, and what data exists to move it with. While the use case is still being shaped, it's usually the most useful artifact: it puts the whole approach on one page and gives everyone something concrete to react to.

## Contents

- [What it's for](#what-its-for)
- [Structure](#structure)
- [Writing guidance](#writing-guidance)
- [Sourcing](#sourcing)
- [Placing it](#placing-it)

## What it's for

Two audiences, one document:

- **Agent creation**, which reads it while it drafts an Agent: the create screen, Auto-draft and the per-field suggestions. It does **not** reach a decision. The harness that decides on each event never reads workspace memory, so a business fact a decision depends on (the ICP, the offerings, channel response rates, timing windows, constraints) must also be written into the Agent body: its `agentPrompt`, a signal's `promptFragment`, an option's `whenToPrefer`. Here alone, it shapes the draft and is then invisible to the Agent.
- **Humans** — the customer reviewing the setup, and colleagues picking up the workspace later.

Write for both. Concrete and specific serves each better than abstract positioning.

## Structure

A shape that works, to adapt rather than follow rigidly:

```markdown
# <Org> — RudderCrew Workspace

## Business context

Who they are, what business they're in, and the facts that shape decisions:
the metric being moved and its current value, channel effectiveness, timing
windows, regulatory or brand constraints.

## Top goals

What this workspace exists to change. Name the outcome, not the mechanism.

## Observe — potential signals

The data available to reason over, grouped by system. Reference real event
names from recon where known.

## Decide — potential options

How to weigh the signals into a choice, and the range of options available.

## Act

What actually happens, on which channel, and the review posture (shadow
vs live).

## Agents

Which agents live here and what each one's scope is.

## Out of scope

What this workspace deliberately does not cover.
```

**Keep workspace scope separate from agent scope.** The workspace describes the organization and its goals; an agent describes one bounded decision loop. Conflating them makes the workspace read as a description of a single agent, which breaks down the moment a second agent is added.

## Writing guidance

**Numbers over adjectives.** "No-show rate is ~45%, up from ~30%" carries more than "high no-show rate." The number is what makes it actionable and what the customer will correct if it's wrong — which is itself valuable.

**Hedge where things are genuinely unsettled.** While the design is still open, "potential signals" and "potential options" are more accurate than declarative headings, and they invite the customer to shape it rather than approve or reject it. Once the design is settled, drop the hedging.

**Mark what's assumed.** If a mapping is inferred rather than confirmed, either say so or turn it into a question you'll ask. Don't let an assumption silently become load-bearing.

**Address the audience directly.** The document speaks to the customer and to the agent — not to the person who commissioned it.

## Sourcing

In descending order of reliability:

1. **Direct customer statements** — call transcripts, shared docs, their own written framing. Their words and their numbers.
2. **Tickets and internal notes** (issue trackers, wikis, chat threads) — use case framing, next steps, contacts. Ticket status lags reality.
3. **Recon** (see `recon.md`) — the real data inventory.
4. **Reasoned inference** — everything else. Label it.

None of 1–3 are mandatory. When they're absent, build from what's available and be explicit about which parts are unconfirmed.

## Placing it

The Crew MCP can read workspace memory (`context_get`) but not write it, by design: one edit changes what every Agent's creation reads. So the context always ends as a paste-ready block (`mcp-map.md` → "The paste-ready artifact pattern"), handed over with where it goes:

1. Read the current context first (`context_get`) and keep what the customer wrote: the new text adds to it or revises it, and says so, rather than replacing it unseen. Write the whole document as one fenced markdown block, with nothing inside it that is not meant to be pasted. Save the same text to a file too (`context.md`), so the user can review it in their editor.
2. Tell the user: open Context in the Crew app (`/context`), replace the text with the block, save, and turn **automatic updates** off. Automatic updates regenerate the document from the workspace's Agents and data and overwrite hand-written text.
3. **Saving needs an admin.** Editing the Context page needs `workspace:manage`, which only the workspace's `admin` role holds; an invited member can read the page but not save it. If the user is a member, they ask a workspace admin (or their Crew contact) to paste it, or to make them an admin under Settings → Members.
4. Read it back with `context_get` once they say it is saved, and check it is the text you wrote.

Nothing waits on this. Agent creation in the app reads the context; the harness that decides on each event never does, so an Agent created over MCP before the context is placed decides exactly as it would after (`What it's for`, above).
