---
description: From a plain brief, the lead-scoring skill drafts a tiered, Shadow-first Agent body with the ICP written into it.
tags: [lead-scoring]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write]
---

Acme Data sells a warehouse-native analytics product to B2B SaaS companies with 50 to 2,000 employees. Heads of data and analytics engineering leads buy it; analysts champion it. Students and agencies never fit, and anyone at acmedata.com is our own staff. Signups reach Crew as `Signed Up` events and pricing visits as `Pricing Viewed`; a booked demo is `Demo Booked`.

Draft a Crew agent that scores these leads and routes them, and save the agent body as agent-body.json in this folder. Don't create anything in Crew yet: I want to review the file first.
