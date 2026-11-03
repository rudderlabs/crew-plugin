---
description: From a brand-new, empty workspace, the workspace-setup skill drafts the context as a block the user pastes, and plans the first Agent Off with one dry run on a list of sample people before any webhook or test events.
tags: [workspace-setup]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write]
---

We just got a brand-new, empty Crew workspace for Acme Fitness, a gym-class booking app with about 40,000 paying members. Members who skip two weeks of classes usually cancel within a month. I want an agent that spots members drifting away and drafts a short win-back email for each one.

Before anything touches real data: write the workspace context we should use and save it as context.md in this folder. Then plan how you would create the agent and try it on five sample members, and save the exact dry-run request you would send as dry-run.json. Don't call any Crew tools yet; explain the plan in a few paragraphs.
