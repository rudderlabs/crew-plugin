# Agent copy rules learned from real runs

Read at step 8. Each rule is here because a real Dry Run or Shadow pass broke without it.
linkedin-outreach's `references/agent-body.json` already carries the general ones (no flattery,
no invented sender, thanks only after an accepted request, no meeting times). Add these for a
researched campaign:

- Connect and Message prompts: "Use a company item only when it is from the last six months and
  about their customers, marketing or data; skip old news and routine pages. Never present a company
  item as the person's own work or decision. If the only hook is weak, leave it out: a plain,
  friendly note beats a forced one."
- Connect and Message prompts: "What research found about their company's stack and how it works
  today is for choosing what to say, never something to state back to them as known."
- Connect and Message prompts, when the talking point is an open job: "An open role at their company
  is why we reached out, never the message: do not name the role, and never sound interested in it
  or as if applying. Say at most that their team is growing, or leave it out. Two people at one
  company get different notes." Without it, a Shadow pass of 20 notes gave 13 copies of "X is hiring
  a Y. I'm at <Company> and would be glad to connect", and one read like a job application.
- Fit rule: exclude people _employed by_ a competing vendor and say "a company that USES those tools
  is fine". Written as "not working at Braze or Iterable", the Agent held a lead because research
  found the lead's company uses Iterable.
- Existing customers: drop them from `leads.csv` rather than relying on the Fit rule, unless the user
  wants them as an upsell. The evidence that a company uses the product often sits in an excerpt
  behind a field the evidence check refused, which the decision never sees.

If your copy of linkedin-outreach predates those general rules, add them too: "Never claim to
know, have seen or admire their work, and no stock flattery such as \"stood out\" or \"impressed
by\", and no congratulations on a new role, promotion or funding: we have not met." and "Never describe yourself or invent anything about the sender (no \"I
work with…\", \"fellow …\"); if you say who you are, say only that you are at <Company>."

## Meeting times: a prompt rule, never a hard constraint

The Reply prompt carries the rule: "When they ask for a demo or a call, or name a day or time,
<DEMO_REPLY>; never propose, accept or agree to a specific day, date or time yourself, and never
commit the team to anything." linkedin-outreach's "Collect the inputs" item 3 says how to fill
`<DEMO_REPLY>`: the product's booking link when its pages have one. "I'll send a few times" only
when someone will: in one run nobody would, and the Agent promised times that never came.

Do not add it as a hard constraint. The judge audits hard constraints only, which is tempting (in the
second run a Reply agreed to "Thursday afternoon" and the judge passed it), but a hard constraint
that fires holds the whole action: as `no_meeting_time` it turned "Does Thursday afternoon work?"
into no reply at all, losing the outcome the Agent exists for. Dry-run that demo request every time
(step 10) and tell the user the judge does not enforce the rule.

## Known limit

Copy rules in a prompt are followed most of the time, not always: in the third run's Shadow pass 2
of 10 notes still invented the sender ("a fellow data leader", "work with data leaders") with the
rule in place. Read every Shadow note, and suggest "needs approval" on the first Live batch.
