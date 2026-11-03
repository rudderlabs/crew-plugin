---
type: llm
weight: 2
---

Judge only the order of the plan and the shape of the test.

PASS if all three hold:

1. The agent is created Off (or as a draft) first, and the first test is a dry run with `preview_tryEvent` on the five sample members together, in one call with a list of events.
2. That dry run comes before any webhook is created and before any test events are sent. A webhook, if the plan mentions one, comes later, to get Shadow decisions or a real event catalog.
3. Nothing is switched on for real members: the agent stays Off or in Shadow, and going Live is left to a person in the Crew app.

FAIL if the plan creates a webhook or sends events before the dry run, dry-runs one member per call, or turns the agent Live.
