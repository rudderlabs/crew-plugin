---
type: llm
---

PASS if the answer carries on with the existing Agent, LinkedIn connection and webhook. Checking that each still works, and reconnecting LinkedIn or making a new webhook only when that check finds it gone (a dropped connection, a missing token file), is fine. FAIL if it plans to connect LinkedIn again, create a new Agent or create a new webhook regardless of what the checks find.
