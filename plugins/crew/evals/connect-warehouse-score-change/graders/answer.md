---
type: llm
weight: 2
---

The user asked for a design, not a build. Judge the design.

PASS if all five hold:

1. A scheduled RudderStack Reverse ETL sync from the scores table (or a SQL model over it) sends each user to a RudderCrew webhook as a track event with one fixed event name, the user's id cast to text as the user id.
2. The decision fires when a user moves into high risk, not on every nightly change of the score: the model computes a band or flag (for example high, medium, low) and the sync maps that instead of the raw `churn_risk`, under Upsert so unchanged rows are not sent again.
3. `last_login_at`, the raw score, and any other column that changes on most nights are left out of the model's output (not only the mapping), because under Upsert a changed row is sent again and makes a new decision.
4. The email column is mapped to `properties.email` and checked as an identifier in RudderCrew before any email is sent.
5. The Agent runs in Shadow (deciding without sending) until a person takes it Live.

FAIL if any point is missing, or if it claims to have built anything, maps the raw score under Upsert without saying every small change makes a new decision, sends every user every night with Full, or says RudderCrew reads Snowflake itself.
