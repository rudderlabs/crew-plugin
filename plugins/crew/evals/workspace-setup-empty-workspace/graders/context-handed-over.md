---
type: llm
---

Judge only how the workspace context reaches Crew.

PASS if the answer hands the context to the user as complete text (a block in the answer, or the saved context.md, with no placeholders left to fill) and tells them where it goes: they, or a workspace admin, paste it into the Context page in the Crew app.

FAIL if it says Claude will save or has saved the context in Crew itself, or leaves the user to work out where the text goes.
