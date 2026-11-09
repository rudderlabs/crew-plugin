# Solution patterns: warehouse data → RudderCrew decisions

A Reverse ETL sync turns each row of a table or SQL model into one track event, and every Agent triggered on that event name decides on it; or, for pattern 4, into an identify call that writes traits. The mechanics are in `SKILL.md`. This file is for the step before them: turning what the user wants into the right shape of model, sync and Agent. Pick the pattern first; the build steps then have no open choices left.

## Contents

- [Decide the shape first](#decide-the-shape-first)
- [Pattern 1: A snapshot decided every run](#pattern-1-a-snapshot-decided-every-run)
- [Pattern 2: Decide when something changes](#pattern-2-decide-when-something-changes)
- [Pattern 3: Entering a set](#pattern-3-entering-a-set)
- [Pattern 4: Warehouse facts as context, not a trigger](#pattern-4-warehouse-facts-as-context-not-a-trigger)
- [Pattern 5: A model's or a scoring job's output](#pattern-5-a-models-or-a-scoring-jobs-output)
- [When this is not the skill](#when-this-is-not-the-skill)

## Decide the shape first

Answer these with the user before writing SQL. Each answer fixes one part of the build.

| Question                                                                                                                 | Fixes                                                                                                                                                            |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Who is the decision about?** A person, or a customer account                                                           | The id column: the person's product `user_id`, or `'account:' \|\| account_id`. An account Agent follows `workspace-setup`'s `references/account-agents.md`      |
| **What should prompt a decision?** Every run; a change; a row entering a set                                             | The pattern (1, 2 or 3), the sync mode (Full or Upsert) and which columns are mapped                                                                             |
| **How fresh must it be?** Minutes, hours, a day, a week                                                                  | The schedule. The sync runs at most every 5 minutes; anything that must happen seconds after a user acts is a product event (`connect-rudderstack`)              |
| **What does the Agent do with the row?** Message the person; tell a team; record a value                                 | The channel, and whether a row needs an email. A webhook or Slack action resolves no recipient; an email action needs `properties.email` on a row about a person |
| **Does the data decide, or inform?** The row itself is the reason to act, or it is background other decisions should see | Pattern 1, 2, 3 or 5 (a track event), or pattern 4 (an identify writing traits)                                                                                  |
| **How many rows, how often?**                                                                                            | Decisions per month, and the model budget they spend. Rows sent per run × runs per month. Agree the number before the first full sync                            |

The arithmetic to show the user every time: **Full** sends every row every run, so decisions per month = rows × runs. **Upsert** sends new and changed rows, so decisions per month = rows that change per run × runs, plus every row once on the first sync. Multiply either by the Agents triggered on the event, and add follow-ups if they are on. Run the model and count; for Upsert, count how many rows changed between two consecutive versions of the table if a history exists, otherwise estimate and watch the first week. A row the Agent's guardrails suppress (`deduplicated`, `rate_limited`) is recorded before any model call, so it spends no model budget, and acts on nothing either.

Two facts shape every pattern. The **first sync of a connection sends every row whatever the mode**, so a pattern that should start quiet needs a plan for that run. And **the sync mode, event type and user identifier of a saved connection cannot be changed**: a change means a new connection, whose first sync sends every row again.

The SQL below is Snowflake's, with each alias double-quoted so it arrives in lower case (`SKILL.md` step 4). On BigQuery and Databricks drop those quotes, which make a string there.

## Pattern 1: A snapshot decided every run

**Fits when the user says:** "every account should have a health tier", "renewal risk for every customer every week", "a Monday report on where each account stands". The decision's value is that it is current for everyone, including the accounts whose numbers did not move.

- **Entity and id:** almost always the account, `account:<id>`. A person variant exists (a weekly engagement tier per user) but is rarer and much larger.
- **Model:** one row per account, the facts the signals read, numbers as numbers.

```sql
SELECT 'account:' || CAST(a.account_id AS VARCHAR) AS "account_id",
       a.plan AS "plan", a.seats AS "seats",
       u.active_users_7d AS "active_users_7d", u.active_users_prev_7d AS "active_users_prev_7d",
       t.open_tickets AS "open_tickets",
       CAST(a.renewal_date AS VARCHAR) AS "renewal_date"
FROM accounts a LEFT JOIN usage_weekly u ON u.account_id = a.account_id
LEFT JOIN tickets_open t ON t.account_id = a.account_id
WHERE a.is_customer
```

- **Sync mode:** Full. Upsert would skip the unchanged accounts, and their tier would go stale downstream. **Schedule:** the cadence of the decision, weekly or daily, as a cron in UTC. **Event name:** `Account Health Snapshot`.
- **Agent:** `account-agents.md` end to end: one signal per aspect (usage trend, support load, commercial position), a Decide Option per tier with `whenNoClearFit: closest_action` so every account gets a tier, one webhook action per tier named for it (`health_red`), or a Slack action for the at-risk tier only. Once an account's event has matched a trigger, its events are kept 15 days, so a signal can compare this snapshot with last week's.
- **Guardrails:** set under the sync interval or the defaults suppress runs: for daily, dedup `20h`, `2` per day, `7` or more per week; for weekly the defaults pass. Follow-ups off (`followUp.enabled: false`): the next snapshot is the next decision, and an Agent created without a `followUp` block has them on.
- **Budget:** rows × runs. 2,000 accounts weekly is about 8,700 decisions a month; daily is about 60,000. A snapshot is the most expensive pattern per row of information, so weekly is the usual answer and daily needs a reason.
- **The pitfall:** a daily snapshot under the default 72-hour dedup window records two days in three as `deduplicated`, and the receiver's table looks like the Agent stopped. Check the first week's decisions for `deduplicated` and `rate_limited` before trusting the downstream table.

## Pattern 2: Decide when something changes

**Fits when the user says:** "when usage drops", "when the score crosses 70", "when an account goes from green to yellow", "tell the AE if it's slipping". Nothing should happen while things stay the same.

- **Entity and id:** account or person, as the change is about.
- **Model:** map a **band computed in SQL**, never the raw number. Under Upsert a row is sent when its values change, so a raw `active_users_7d` of 41 → 40 is a decision and 40 → 41 is another. A band changes only when it matters.

```sql
SELECT 'account:' || CAST(account_id AS VARCHAR) AS "account_id",
       CASE WHEN active_users_7d < 0.5 * active_users_prev_7d THEN 'falling_fast'
            WHEN active_users_7d < 0.8 * active_users_prev_7d THEN 'falling'
            WHEN active_users_7d > 1.2 * active_users_prev_7d THEN 'growing'
            ELSE 'steady' END AS "usage_band",
       CASE WHEN days_to_renewal <= 30 THEN 'inside_30'
            WHEN days_to_renewal <= 90 THEN 'inside_90' ELSE 'later' END AS "renewal_band",
       plan AS "plan"
FROM account_usage_weekly WHERE is_customer
```

- **Sync mode:** Upsert. **Schedule:** as often as the bands are rebuilt, usually daily. **Event name:** `Account Usage Changed`, `Lead Score Band Changed`.
- **Agent:** signals read the band; Options per band worth acting on, `whenNoClearFit: hold_off` so a change into `steady` holds. For direction, the previous event in the entity's window works only while it is under 15 days old. When direction matters beyond that, keep a band-history table and map `previous_band`, the band before the current one, which changes only when the band does. Never map last run's band: it changes one run after the band does, so every change costs two decisions.
- **Guardrails:** a change the guardrails suppress is not retried. Under Upsert the row is not sent again until it changes again, so a second band change inside the deduplication window is recorded as `deduplicated` and lost. Keep the window shorter than the time between two changes that both matter, or accept that the later one is dropped. Follow-ups per the use case.
- **Budget:** rows that change band per run × runs, plus every row on the first sync. With well-chosen bands a few percent of rows change per day; a band cut too fine behaves like Full.
- **The pitfall:** one column that moves every run, `days_to_renewal`, `last_seen_at`, `snapshot_date`, `updated_at`, turns Upsert into Full. Leave such columns out of the model itself, not only out of the mapping: a test run showed that an unchanged row is not sent again, but not whether RudderStack compares the mapped columns or the whole row. Keep dates as fixed text (`renewal_date`), and let the Agent count days from them.

## Pattern 3: Entering a set

**Fits when the user says:** "new trial users who reach 80% of their limit", "accounts that just hit their first 100 API calls", "whenever someone qualifies", "keep sending the people who join this audience". The model is the filter; a row's arrival is the event.

- **Entity and id:** usually a person (`user_id`, the one the product sends, so the row joins their profile and recent events); an account for milestones per customer.
- **Model:** the set's definition as a `WHERE` clause, one row per member, with only the columns that describe why they are in it. A Lookout or RudderStack audience's filter is rewritten here as SQL: an audience source cannot connect to a Webhook destination.

```sql
SELECT CAST(u.user_id AS VARCHAR) AS "user_id", u.email AS "email", u.plan AS "plan",
       LISTAGG(l.limit_name, ', ') WITHIN GROUP (ORDER BY l.limit_name) AS "limits_near"
FROM trial_users u JOIN trial_limits l ON l.user_id = u.user_id
WHERE u.trial_ends_at > CURRENT_DATE AND l.limit_pct_used >= 80
GROUP BY u.user_id, u.email, u.plan
```

A user near two limits is still one row, its `limits_near` listing both in a fixed order (`STRING_AGG(l.limit_name, ', ' ORDER BY l.limit_name)` on BigQuery and Postgres). Reaching a further limit changes that list, so the member is sent again under Upsert: a new reason to act, and one more decision in the budget. To act only on one limit, filter to it (`AND l.limit_name = 'api_calls'`) and drop the aggregate.

- **Sync mode:** Upsert, so a member is sent once, on entry, as long as the model's columns stay the same while they are in the set. That is why the model leaves out `limit_pct_used`: it rises 80 → 85 → 90 and would send the member again each time. If each step should be a decision, map a band (`'80_to_90'`, `'over_90'`) and count those steps in the budget. **Schedule:** hourly to daily. **Event name:** `Trial Limit Approaching`, `Account Milestone Reached`.
- **Agent:** the row is the reason to act, so Observe can be thin; Decide's Options are the messages worth sending; Act emails the person (`properties.email` mapped, and marked as an identifier after the first arrival, `SKILL.md` step 7) or tells the team. Follow-ups are often wanted here: a person near a limit gets a short sequence.
- **Guardrails:** the defaults fit.
- **Budget:** entries per run × runs, plus the whole set on the first sync. Small after day one.
- **The pitfall:** **the first sync sends everyone already in the set**: three months of trial users near their limit, decided and, if Live, messaged, in one run. Two ways to start quiet, and they do not mix:
  - **A launch cutoff kept in the model for good:** `AND entered_at >= '<YYYY-MM-DD HH:MI:SS>'`, the moment the model goes in, as a fixed literal that is never removed, so members from before launch never enter. Write a full timestamp in the time zone `entered_at` is stored in: a bare date lets in everyone who qualified earlier that day. Removing it later sends all of them at once. It needs a column that says when each member qualified.
  - **A baseline sync with the Agent Off:** run `SKILL.md` step 7's one-row test in Shadow, move the Agent Off, put the full query back and sync once: every current member arrives, and an Off Agent decides on none of them, then or later. Move the Agent back to Shadow only after `get_retl_source_syncs` shows the baseline run succeeded with no failed rows; while it has failed rows, keep the Agent Off and sync again. From then on only new members are sent. A new connection's first sync sends everyone again; what a partly failed baseline run resends was not checked in a test run, so keep the Agent Off until a run is clean.

  Members who enter while the Agent is in Shadow get no Live decision unless they are sent again after a person takes it Live: `SKILL.md` step 8, "When a person takes the Agent Live".

  Also: Upsert never reports a row that left the set, so the Agent never learns someone stopped qualifying. Not checked in a test run: whether a row that leaves and later returns is sent again.

## Pattern 4: Warehouse facts as context, not a trigger

**Fits when the user says:** "the agent should know each user's plan and ARR, but that lives in the warehouse", "our events don't carry the CSM owner", "accounts have a tier and the people at them should be treated by it". The facts are not a reason to act; they should be in front of Agents that decide on product events.

- **Entity and id:** the person, under the `user_id` the product sends; anything else writes traits onto a profile no event reaches.
- **Model:** one row per person with the facts as columns. **Account facts are denormalized onto each person's row** (`account_tier`, `account_arr`, `csm_owner`): a Reverse ETL connection sends identify or track, never a group call, so there is no account record to attach them to.

```sql
SELECT CAST(u.user_id AS VARCHAR) AS "user_id", u.plan AS "plan", u.seats AS "seats",
       a.tier AS "account_tier", a.arr AS "account_arr", a.csm_owner AS "csm_owner",
       CAST(a.renewal_date AS VARCHAR) AS "account_renewal_date"
FROM users u JOIN accounts a ON a.account_id = u.account_id WHERE u.is_active
```

- **Connection:** event type **Identify**, columns mapped to `traits.<name>`, the id column as the user identifier. An identify writes traits onto the person's profile, which every Agent's decision on that person can read. **Sync mode:** Upsert, so only changed facts are rewritten. **Schedule:** daily is plenty.
- **Agent:** none for this connection. The Agents that benefit are the ones already triggered on product events (`Trial Started`, `Pricing Page Viewed`): their signals and Options can name the traits (`when account_tier is enterprise, route to the AE`).
- **Guardrails and budget:** no decisions, no budget, as long as no Agent triggers on `identify`.
- **The pitfall:** every row arrives as the event **`identify`**, and an Agent triggered on `identify` (a signup-welcome Agent often is) decides on every row of the first sync and on every change after. Check `agent_list` for one before the first sync; if it exists, it needs a trigger condition that excludes these rows, or a different trigger. Also, the identify sets traits but writes nothing into the person's event window, so a signal reads the facts as they are now, not as they were.

For facts an **account Agent** should see, do not use this pattern: put them on the snapshot row itself (pattern 1). For a person Agent that should act on an account's change (the power users of an account that just went red), send a track per person with the account's facts as properties, so each person is decided on under their own id and guardrails (`account-agents.md` → "When the people matter too").

## Pattern 5: A model's or a scoring job's output

**Fits when the user says:** "our data team writes a churn score nightly", "we have a propensity model", "lead scores in a table, the agent should work the hot ones". A score table is pattern 2 or 3 wearing numbers: decide which before mapping anything.

- **Entity and id:** whatever the score is about; a lead score is per person, a churn score is usually per account.
- **Model:** band the score in SQL, and either send every scored entity's band (pattern 2) or only those over a threshold (pattern 3). Never map the raw score or the `scored_at` column: a model rerun writes a new float for every row, which under Upsert sends every row every night.

```sql
SELECT 'account:' || CAST(account_id AS VARCHAR) AS "account_id",
       CASE WHEN churn_probability >= 0.7 THEN 'high'
            WHEN churn_probability >= 0.4 THEN 'medium' ELSE 'low' END AS "churn_band",
       top_driver_at_band_change AS "top_driver"
FROM churn_predictions_latest
```

- **Sync mode:** Upsert. **Schedule:** a cron after the scoring job finishes, so a half-written table is never read. **Event name:** `Churn Risk Band Changed`, `Lead Score Qualified`.
- **The driver:** a model's `top_driver` can change while the band stays put, and each change sends the row again. Take it from the night the band last changed (a band-history table, as in pattern 2), so it moves only with the band; or leave it out, or count its changes in the budget.
- **Agent:** the score is a reading the data team already made, so one signal restating it adds nothing (`oda-design.md` → "what earns a signal"). The Agent's work is what to do about it: Options per band, with the model's `top_driver` as the thing the message or the Slack post is about. Account scores follow `account-agents.md`.
- **Guardrails:** as pattern 2: a band change the deduplication window suppresses is lost under Upsert, so keep the window shorter than the time between two band changes that both matter. Follow-ups off for an account Agent; per the use case for a person Agent.
- **Budget:** band changes per night × 30, plus every row once. A model that flips many rows between bands every night is noise upstream; widen the bands, or score weekly.
- **The pitfall:** the scoring job rebuilds its table and the sync reads it mid-write, or reads an empty table, and the next run may then send every row as new (not checked in a test run). Read from a `_latest` view the job swaps atomically, and schedule the sync after the job's usual finish time.

## When this is not the skill

| The user wants                                                                                                               | Use                                                                                                                                                                 |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A decision within seconds of something a person did (a signup, a pricing page visit, a checkout abandoned)                   | `connect-rudderstack`: the product's own event stream. A sync runs at most every 5 minutes, and the row would say what happened, not that it is happening now       |
| A reviewed list of up to a few hundred people, sent once (a webinar list, a Lookout audience worked this week, a CRM export) | `send-list`: the user approves each row and the send happens once, from Claude Code. A list that should keep sending the people who join it later is pattern 3 here |
| To build or change the Agent itself: its signals, Options, message instructions, trigger                                     | `workspace-setup`, before this skill. This skill assumes the Agent exists and has been dry-run on hand-written rows                                                 |
| To review or correct an Agent's recent decisions                                                                             | `calibrate`                                                                                                                                                         |
| To load events **into** the warehouse (a Snowflake, BigQuery or Redshift destination in RudderStack), or to fix a dbt model  | RudderStack's own documentation and plugins. Nothing in it reaches a RudderCrew Agent until a table exists and one of the patterns above sends it                   |

Two combinations come up often. An account snapshot (pattern 1) beside a person Agent is how "tell the CSM about the account, and nudge its power users" is built: two Agents, two connections, one warehouse. The person Agent either reads the account's facts as traits (pattern 4) when each person's next product event arrives, or, to nudge them as soon as the account changes, decides on a track event per person that carries the account's facts. And a growing list (pattern 3) that starts as a `send-list` review is the usual path for a team that wants to see the first hundred people before a schedule takes over: the reviewed query becomes the model.
