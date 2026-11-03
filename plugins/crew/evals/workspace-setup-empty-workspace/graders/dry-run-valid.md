---
type: llm
focus: { source: file, path: dry-run.json }
---

The file is the request Claude would send to Crew's `preview_tryEvent` tool. Judge only its shape.

PASS if all four hold:

1. It names the Agent one way: either a `draftId`, or a `skillId` together with a `version` (a placeholder value for an id that does not exist yet is fine).
2. `event` is a list (not a single object) with one entry per sample member, five in all, for five different members.
3. Every entry has an `eventName` and `properties` holding the facts the agent needs (for example last class attended, classes booked, plan).
4. The members are fictional: no real person's name or email (an `@example.com` address, or none, is fine).

FAIL if any of the four is missing, or if `event` is empty.
