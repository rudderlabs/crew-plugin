---
description: A nightly model score in the warehouse reaches the connect-warehouse skill, and the design decides on a move into the high-risk band rather than on every change of the raw score.
tags: [connect-warehouse]
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

our data science team writes a churn score for every user each night into snowflake, table ANALYTICS.CHURN_SCORES with user_id (a number), email, churn_risk (0 to 1), plan and last_login_at. when someone becomes high risk we'd like a RudderCrew agent to send them a personal check-in email from their CSM. how would you set this up? don't build anything yet, just tell me the design.
