---
description: A trigger on entering a set, with thousands already in the set, reaches the connect-warehouse skill, and the design keeps the first sync from deciding on everyone already there.
tags: [connect-warehouse]
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

We have a dbt model fct_trial_usage in Snowflake (user_id, email, pct_of_plan_limit, trial_started_at, crossed_80_at). About 3,000 current trial users are already above 80%. From now on, when a trial user crosses 80% of their plan limit, we want our RudderCrew upgrade agent to email them once. How would you design this? Don't build anything.
