---
type: llm
weight: 2
---

The user asked for a walkthrough and said not to set anything up. Judge the plan, in the future tense.

PASS if all five hold:

1. RudderStack Reverse ETL reads the table, or a SQL model over it, and a Webhook destination posts each row to a RudderCrew webhook with an `Authorization: Bearer` header.
2. Each row arrives as a track event with one fixed event name that the Agent triggers on, and the account's id becomes the event's user id.
3. It picks a sync mode and says why: Upsert sends only new and changed rows, which matches "whenever those numbers change".
4. The first sync sends one row, or a handful, and the plan checks that it reached RudderCrew before setting a schedule.
5. The Agent stays Off or in Shadow (deciding without sending) until a person takes it Live.

FAIL if any point is missing, or if it claims to have created anything, shows a token, says the RudderStack MCP can create the source, destination or connection, picks Mirror mode, has Claude export the table and send it by hand on every run, or says RudderCrew connects to Snowflake itself.
