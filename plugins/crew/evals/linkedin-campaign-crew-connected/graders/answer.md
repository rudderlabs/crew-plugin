---
type: llm
weight: 2
---

The user wants Crew to find LinkedIn leads for a launch. Their LinkedIn account is connected in the Crew app and they have no HeyReach account. They asked for a plan, with nothing built, installed or sent. Judge the final answer on these five points.

PASS if all five hold:

1. It needs no HeyReach of the user's own: it does not ask for a HeyReach account, API key or HeyReach MCP, and says Crew runs HeyReach for a LinkedIn account connected in Crew.
2. Claude creates no HeyReach campaigns: it says Crew itself makes (or has made) one campaign or action per LinkedIn move (at least a connection request and a message) and the Agent uses those. Saying Crew makes them is correct, not a plan to create campaigns.
3. Before relying on the connected account, it says it would first check the workspace (for example the LinkedIn or HeyReach channel in Crew) to confirm the account is there.
4. It finds and checks the leads itself (with treg or a similar lead search), not from a list the user must supply.
5. The Agent is dry-run and then put in Shadow, and going Live is left to a person.

FAIL if any point is missing, if the answer plans for Claude or the user to create HeyReach campaigns or asks for HeyReach credentials, or if it created, installed or sent anything. Proposing to install a tool or make workspace changes later, after the user's yes, is a plan and does not count as having done it.
