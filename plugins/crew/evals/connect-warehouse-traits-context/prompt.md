---
description: Warehouse facts that should inform existing Agents, not trigger one, reach the connect-warehouse skill, and the design writes them as traits with an identify connection after checking for Agents triggered on identify.
tags: [connect-warehouse]
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

Our trial onboarding agent in RudderCrew already decides on product events like Trial Started and Feature Used. It should also know each user's plan, seat count, ARR and their CSM's name, but that only lives in our Postgres replica (public.subscriptions, keyed by the same user_id our app sends). How do we get that to the agent? Just the design, please; don't set anything up.
