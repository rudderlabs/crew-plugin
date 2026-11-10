---
type: llm
weight: 2
---

The user wants warehouse facts in front of an Agent that already decides on product events. Judge the design.

PASS if all four hold:

1. A RudderStack Reverse ETL sync from `public.subscriptions` (or a SQL model over it) sends each user as an identify call that writes the facts as traits on that person's profile, keyed by the same user id the app sends (as text).
2. No new Agent or trigger is built for these rows: the existing onboarding Agent reads the traits when it decides on its product events.
3. It warns that every row arrives as `identify`, so any Agent triggered on `identify` would decide on each row, and checks for such an Agent before the first sync.
4. It runs on a schedule (Upsert or similar, daily or so) and nothing is claimed to be built.

FAIL if it sends the rows as a track event for an Agent to decide on, uses RudderStack group calls, says RudderCrew reads Postgres itself, or claims to have set anything up.
