---
type: llm
weight: 2
---

The person returns to a LinkedIn outreach Agent that is already built and in Shadow with 20 decisions. Judge the final answer.

PASS if all four hold:

1. It starts by reading what exists in the workspace (the channel still connected, the Agent and its state, the Shadow decisions) before proposing changes.
2. It does not propose connecting LinkedIn again, creating a new Agent or creating a new webhook.
3. Next steps are: read the 20 Shadow decisions with the person, then either send more leads (only people not already decided on) or hand over the Live switch.
4. Going Live is left to the person in the Crew app.

FAIL if it restarts from collecting inputs, or proposes to resend the same 20 people.
