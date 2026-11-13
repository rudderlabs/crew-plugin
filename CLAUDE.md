# crew-plugin

This repository is public. People outside RudderStack read all of it, and every customer's Claude
reads the plugin's files. Public text here means more than the files: skills, references, evals,
both READMEs and `llms.txt`, and also commit messages, pull-request titles and descriptions, review
replies and release notes.

## Public text

Write all of it as product documentation: what changed, and why, in terms of what the product does.

- Say what a change does and the behaviour behind it ("setup installs only the Crew plugin; a skill
  checks for Python at the step that runs a script"), never where the idea came from.
- Never name or describe a person, a customer, a prospect, a partner, a call, a demo, a
  user-testing session or anyone's setup ("watching a first-time user", "on the call with…",
  "their workspace"). Evidence for a rule is a generic run ("in an onboarding-email Agent, the
  first dry run…"), as [`plugins/crew/README.md` → Adding a skill](plugins/crew/README.md#adding-a-skill)
  says.
- No internal names: private repositories, internal hosts, Slack channels, tickets, workspace or
  Agent ids, pull-request numbers in other repositories, staff names, or dates of internal events.
- Context that is internal (who asked, which call, which customer) belongs in the internal tracker
  or the private product repository, never here.

**Commit messages are public too.** A squash merge here copies every commit message on the branch
into `main`'s history, so reword a commit (amend, or rebase) before the pull request merges, not
after.

Automated checks catch ids, hosts and pull-request numbers, never a sentence about a call: read
your own text, commit messages and the pull-request description included, before you push.
