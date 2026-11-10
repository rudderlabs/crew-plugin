---
description: An account health ask whose data already sits in a warehouse, with no mention of Reverse ETL, reaches the connect-warehouse skill, and the plan sends one snapshot event per account on every scheduled run.
tags: [connect-warehouse]
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

We want to score every customer account green, yellow or red each week from product usage, support tickets and renewal dates, and tell the account manager when one turns red. All of that already lives in BigQuery, rolled up per account by dbt. We use RudderStack and just got a RudderCrew workspace. What would this look like? A few paragraphs; don't build anything yet.
