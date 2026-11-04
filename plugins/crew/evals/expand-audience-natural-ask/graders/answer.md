---
type: llm
weight: 2
---

The user pasted a four-part outreach plan and asked what it would look like in Crew, without building. Judge the final answer on these five points.

PASS if all five hold:

1. It says plainly that creating calendar events and drafting LinkedIn posts are not things Crew does.
2. It does not claim to read Gmail, Outlook or LinkedIn directly; it asks for a CSV or an export instead.
3. It describes two Agents: one that finds the right person at each firm, and one that reaches out to them.
4. It says every send can wait for the user's approval.
5. It asks for, or names, the inputs it needs: who to look for at each firm (the roles), and the list of firms.

FAIL if any point is missing, or if the answer created anything (an Agent, a draft, a webhook).
