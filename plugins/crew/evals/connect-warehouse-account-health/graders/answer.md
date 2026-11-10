---
type: llm
weight: 2
---

The user described an account health score whose inputs already sit in BigQuery, and asked what it would look like without building. Judge the plan.

PASS if all four hold:

1. The data reaches RudderCrew through a scheduled RudderStack Reverse ETL sync from the dbt table (or a SQL model over it) into a Webhook destination pointed at a RudderCrew webhook.
2. Each run sends one track event per account, under one fixed event name, with the account's id as the user id and the account's numbers as properties.
3. It makes sure every account is sent on every weekly run, not only the accounts whose numbers changed: Full sync mode, or a column that changes each run such as the snapshot date. Saying only "Upsert" with no such column fails this point.
4. Green, yellow and red are the Agent's choices, and the Agent runs in Shadow (deciding without sending) until a person takes it Live.

FAIL if any point is missing, or if it claims to have created anything, says RudderCrew reads BigQuery itself, sends the accounts as RudderStack `group` calls, or says the RudderStack MCP can create the sync.
