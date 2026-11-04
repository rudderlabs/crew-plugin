---
description: From an ICP and a CSV of accounts, the skill drafts the Expand Agent body and the loopback mapping as files, Shadow-first, without the Crew MCP.
tags: [expand-audience]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Bash]
---

We sell a data platform and want partnerships with consultancies. I have accounts.csv with columns company_domain, company and segment (about 60 small consulting firms). The person I want at each is whoever runs partnerships with data vendors: titles like Head of Partnerships, VP Alliances, Director of Channel. Our own domain is example.com. The workspace has a HeyReach channel whose profile identifier is linkedin_url. I can't give you the Crew MCP in this sandbox, so draft the Expand Agent body as expand-agent.json and the loopback webhook mapping as loopback-mapping.json in this folder, with the lead event named "Partner Lead Found", and tell me the next steps. Don't create anything in Crew.
