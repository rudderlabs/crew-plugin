---
description: In a workspace that already receives RudderStack events and has a Live agent, the workspace-setup skill builds on what exists, creating no second webhook or destination, and puts the Live agent in front of the user before any test event.
tags: [workspace-setup]
max_turns: 15
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

Our Crew workspace is already set up: last week we added a RudderStack destination, and Crew's Events page shows `Signed Up` and `Trial Started` arriving all day. We also have one agent that is Live: it emails a welcome note to everyone who signs up, triggered on `Signed Up` and on identify calls. Now I want a second agent that nudges trial users who stall in their first week. Walk me through how you'd build and test it in a few paragraphs; don't run anything yet.
