---
type: llm
---

The user asked for a walkthrough and said not to set anything up. Judge the plan, in the future tense.

PASS if the plan:

1. creates a Crew webhook and has the user add a Webhook destination in RudderStack pointed at its URL with an `Authorization: Bearer` header, connected to their existing sources;
2. checks what is already connected first (existing webhooks, destinations or events) rather than always creating new ones;
3. checks that events arrive in Crew before relying on them; and
4. keeps any agent Off or in Shadow (deciding without sending) until a person takes it Live.

FAIL if it claims to have created or connected anything, shows a token or other credential, says the RudderStack MCP can create the destination, tells them to run `rudder-cli import workspace` to add it, asks them to install a new SDK or change their tracking code to send to Crew, or switches anything on for real customers.
