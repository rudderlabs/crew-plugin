---
type: llm
focus: { source: file, path: agent-body.json }
weight: 2
---

The file is a Crew Agent body. Judge only these four points.

PASS if all four hold:

1. `skills` has separate signals for the company's fit, the person's role, and their intent (three or more signals), not one overall score signal.
2. `decisionLogic.options` has one option per tier (for example Hot, Warm and Cold), each linked by `actId` to an act.
3. The lowest tier (Cold or its equivalent) maps to an act that owns an action policy, such as a webhook that records it. It is not left to "no action", "hold" or `hold_off`.
4. The ICP (B2B SaaS, 50 to 2,000 employees, heads of data or analytics engineering leads) is written in the body text itself: the `agentPrompt`, a signal's `promptFragment` or an option's `whenToPrefer`.

FAIL if any of the four is missing.
