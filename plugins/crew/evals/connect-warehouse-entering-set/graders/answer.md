---
type: llm
weight: 2
---

The user wants a decision when a trial user enters a set, and says 3,000 users are already in it. Judge the design.

PASS if all four hold:

1. A scheduled RudderStack Reverse ETL sync from a model that selects the users at or above 80% sends each one as a track event with a fixed event name the Agent triggers on, the user id cast to text, and the email mapped to `properties.email`, under Upsert.
2. It deals with the 3,000 users already in the set before the first full sync: a launch cutoff kept in the model for good (for example on `crossed_80_at`), or a baseline sync while the Agent is Off, or it asks the user whether those users should be emailed. It must not let the first sync email all of them without saying so.
3. `pct_of_plan_limit`, and any other column that keeps changing while a user stays in the set, is left out of the model's output, so each user is sent, and emailed, once.
4. The Agent runs in Shadow (deciding without sending) until a person takes it Live.

FAIL if any point is missing, or if it claims to have built anything, or says RudderCrew reads Snowflake itself.
