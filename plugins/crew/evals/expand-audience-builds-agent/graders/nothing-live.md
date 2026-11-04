---
type: llm
weight: 1
---

The user asked for two files and the next steps, and said not to create anything in Crew. Judge the transcript and the files it wrote.

PASS if all three hold:

1. Nothing was taken Live: `launchMode` is never set to `live`, Claude never says it will switch an Agent Live, and the answer says the Live switch is the user's.
2. The body file's `agentToolNames` includes `research_account`.
3. The body file's `decisionLogic.whenNoClearFit` is `hold_off`.

FAIL if any of the three is missing.
