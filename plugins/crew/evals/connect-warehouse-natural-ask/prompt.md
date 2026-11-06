---
description: A plain ask to feed a Snowflake table into RudderCrew reaches the connect-warehouse skill, and the plan is a RudderStack Reverse ETL sync into a RudderCrew webhook, tested on one row before it is scheduled.
tags: [connect-warehouse]
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

Our data team keeps a Snowflake table with one row per customer account: this week's active users, open support tickets and days to renewal. It is rebuilt every night. We want a RudderCrew agent to decide on an account whenever those numbers change. How do we get that table into Crew? Walk me through it in a few paragraphs; don't set anything up yet.
