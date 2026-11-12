# Crew plugin for Claude

[RudderCrew](https://crew.rudderstack.com) (Crew) decides, per person and on every event, what to do next and writes the message. This repo is Crew's plugin for Claude: one install connects Claude to your Crew workspace and adds the skills that set it up and build its Agents. Claude takes an Agent as far as Shadow, where it decides on real events and sends nothing, so your team reviews real decisions before anything reaches a customer.

## What you get

| Skill                                                                     | Ask for it with                                                                |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| [`workspace-setup`](plugins/crew/skills/workspace-setup/SKILL.md)         | "Build an Agent that welcomes new signups, dry-run it, then take it to Shadow" |
| [`connect-rudderstack`](plugins/crew/skills/connect-rudderstack/SKILL.md) | "Send our RudderStack events to Crew"                                          |
| [`connect-warehouse`](plugins/crew/skills/connect-warehouse/SKILL.md)     | "Each row of our Snowflake accounts table should trigger an Agent every week"  |
| [`lead-scoring`](plugins/crew/skills/lead-scoring/SKILL.md)               | "Score our inbound leads and send the hot ones to sales"                       |
| [`send-list`](plugins/crew/skills/send-list/SKILL.md)                     | "Send this list of trial users to our onboarding Agent"                        |
| [`calibrate`](plugins/crew/skills/calibrate/SKILL.md)                     | "Review this Agent's last decisions with me"                                   |
| [`expand-audience`](plugins/crew/skills/expand-audience/SKILL.md)         | "Find the right person at each of these companies and reach out"               |
| [`linkedin-outreach`](plugins/crew/skills/linkedin-outreach/SKILL.md)     | "Turn this LinkedIn leads file into an outreach Agent"                         |
| [`linkedin-campaign`](plugins/crew/skills/linkedin-campaign/SKILL.md)     | "Run a LinkedIn campaign for our launch"                                       |

The plugin also connects the Crew MCP server (`https://crew.rudderstack.com/mcp`) and adds a hook that checks every Agent Claude writes. [`plugins/crew/README.md`](plugins/crew/README.md) says what each skill does and needs.

## Before you start

- **A Crew workspace you can sign in to.** Crew is invite-only today: the RudderStack team sets up the workspace and invites you, and there is no self sign-up. Without an invite the plugin installs, but the sign-in finds no workspace: ask your RudderStack contact first. Your role in the workspace decides what Claude can do.
- **Workspace features.** Some skills use a feature switched per workspace, such as Profile enrichment (research about a person or company) or the HeyReach channel (the LinkedIn skills). [Workspace features](plugins/crew/README.md#workspace-features) lists each one, whether a new workspace has it, and who changes it. When one is off, the skill that needs it says what to ask for and carries on without it.
- **Python 3.8 or later, run as `python3`,** for the skills' scripts and the hook. On Windows, check that `python3 --version` works in the shell Claude Code uses.
- **No channels to start.** Shadow needs none. Connect channels in the Crew app before an Agent goes Live.

## Install

### Claude Code

This covers Claude Code in a terminal, in an IDE, and in the Code tab of the Claude desktop app.

**The quick way.** Paste this into Claude Code:

```
Follow https://raw.githubusercontent.com/rudderlabs/crew-plugin/main/llms.txt to set up Crew.
```

Claude installs the plugin, asks you to reload and sign in, checks which workspace you reached, and hands you to the skills. [`llms.txt`](llms.txt) is the script it follows.

**By hand.** Inside Claude Code:

```
/plugin marketplace add rudderlabs/crew-plugin
/plugin install crew@rudder-crew
/reload-plugins
```

Or from a terminal, then start a new Claude Code session:

```bash
claude plugin marketplace add rudderlabs/crew-plugin
```

```bash
claude plugin install crew@rudder-crew
```

This is what a successful install prints:

```
$ claude plugin marketplace add rudderlabs/crew-plugin
Cloning repository (timeout: 120s): git@github.com:rudderlabs/crew-plugin.git
Clone complete, validating marketplace…
✔ Successfully added marketplace: rudder-crew (declared in user settings)

$ claude plugin install crew@rudder-crew
Installing plugin "crew@rudder-crew"...
✔ Successfully installed plugin: crew@rudder-crew (scope: user)

$ claude plugin list
  ❯ crew@rudder-crew
    Version: <the version in plugins/crew/.claude-plugin/plugin.json>
    Scope: user
    Status: ✔ enabled
```

Without a GitHub SSH key, the first line is followed by `SSH clone failed, retrying with HTTPS` and the install carries on. You need no GitHub account.

**Sign in.** Run `/mcp`, pick `plugin:crew:crew`, then **Authenticate**. The browser sign-in picks your Crew workspace, and one sign-in reaches one workspace. Then ask Claude "which Crew workspace am I connected to?": it should name yours.

**Your RudderStack data (recommended).** To let Claude read your RudderStack sources, event volumes and live events, also install RudderStack's own plugin, then sign in to `plugin:rudder-core:rudderstack` the same way:

```
/plugin marketplace add rudderlabs/rudder-agent-skills
/plugin install rudder-core@rudder-agent-skills
```

### claude.ai and Cowork

Members install nothing. An organization Owner adds the plugin to the organization's library (**Organization settings → Plugins & skills**, from the GitHub repo `rudderlabs/crew-plugin`). Each member then connects Crew when Claude asks. The plugin also shows up in Claude Code for anyone signed in with that account. The body-check hook runs in Claude Code and Cowork. claude.ai chat runs no hooks, so there the skills run the check themselves.

### Other agents and MCP clients

The Crew MCP server is `https://crew.rudderstack.com/mcp` (Streamable HTTP, OAuth sign-in). The skills are plain `SKILL.md` folders under [`plugins/crew/skills/`](plugins/crew/skills); load them the way your runtime loads skills. Only Claude is tested.

## Your first Agent

After signing in, ask for the work in plain words, such as "build an Agent that welcomes new signups". The `workspace-setup` skill takes it in steps, and asks for your yes before it publishes a change, moves an Agent to Shadow, creates a webhook or sends events:

1. **Claude reads your workspace** and tells you what already exists, so nothing is created twice.
2. **It creates the Agent Off.** An Off Agent decides nothing and sends nothing.
3. **It dry-runs the Agent on five to ten made-up people** and shows you every draft. Nothing is sent, and no events are needed yet. Say what to change: Claude edits a working copy and runs it again, and publishes once you say the drafts are right.
4. **It connects your RudderStack events,** if you use RudderStack: a Webhook destination sends them to Crew (the `connect-rudderstack` skill). They keep arriving after the Agent moves to Shadow.
5. **Optionally, Calibrate.** Once real trigger events have arrived, Claude replays about ten of them and you mark each decision right or wrong. With test events only, this comes after step 7.
6. **It moves the Agent to Shadow,** after telling you how often the trigger fires. In Shadow the Agent decides on each new trigger event and sends nothing. Read the decisions on the Decisions page in the Crew app.
7. **Without RudderStack, it sends test events from Claude Code,** now that the Agent is in Shadow. Crew decides only on events that arrive while an Agent is on and never replays earlier ones, so test events sent any sooner would leave the Decisions page empty.
8. **You take it Live in the Crew app:** connect the channels the Agent sends on, then switch it Live. Claude never turns an Agent Live. Claude also hands you the workspace context to paste on the Context page; only a workspace admin can save it, and nothing waits on it.

## Update, try, remove

| To                             | Run                                                                                             |
| ------------------------------ | ----------------------------------------------------------------------------------------------- |
| Update                         | `claude plugin marketplace update rudder-crew`, then `claude plugin update crew@rudder-crew`    |
| Try it for one session         | `claude --plugin-dir <your clone>/plugins/crew`                                                 |
| Install from a clone or a fork | `claude plugin marketplace add <your clone>`, then `claude plugin install crew@rudder-crew`     |
| Remove                         | `claude plugin uninstall crew@rudder-crew`, then `claude plugin marketplace remove rudder-crew` |

Restart Claude Code (or run `/reload-plugins`) after an update.

## If something goes wrong

| You see                                                                     | What it means and what to do                                                                                                                                                                                                                             |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No `plugin:crew:crew` in `/mcp` after installing                            | The session started before the install. Run `/reload-plugins --force`, or start a new session.                                                                                                                                                           |
| The sign-in is refused, finds no workspace, or the server fails right after | Your account has no role in a Crew workspace yet. Ask your RudderStack contact for an invite.                                                                                                                                                            |
| `403 insufficient_scope`                                                    | Your role in that workspace holds none of the permissions the tools need. A workspace admin changes it in Crew under Settings → Members.                                                                                                                 |
| `FORBIDDEN: Missing permission: <slug>`                                     | That one step needs a role with that permission. Everything else still works.                                                                                                                                                                            |
| `Profile enrichment is not enabled for this workspace`                      | This workspace has Profile enrichment off. [Workspace features](plugins/crew/README.md#workspace-features) says who turns it on; the skill carries on without it.                                                                                        |
| `python3: command not found`, or a script fails on an older Python          | Install Python 3.8 or later.                                                                                                                                                                                                                             |
| Connected to the wrong workspace                                            | Clear the Crew server's authentication in `/mcp`, then sign in again.                                                                                                                                                                                    |
| The Decisions page is empty after the Agent went to Shadow                  | Shadow decides only on trigger events that arrive after it is on. Test events sent while the Agent was Off are not replayed, and Crew ignores a repeat of the same send: ask Claude to send them again under a new `--run` label, or wait for real ones. |
| A script fails, or the body check never reports, on Windows                 | Both run `python3`. Python from python.org often installs only `python` and `py`; make `python3 --version` work in the shell Claude Code uses.                                                                                                           |

## What's in this repo

```
.claude-plugin/marketplace.json   the rudder-crew marketplace, listing one plugin: crew
llms.txt                          the one-line setup, written for an agent to follow
plugins/crew/                     the plugin: skills, the Crew MCP connection, the body-check hook
plugins/crew/evals/               eval cases, run with: claude plugin eval plugins/crew
```

Adding or changing a skill: [plugins/crew/README.md → Adding a skill](plugins/crew/README.md#adding-a-skill).

## Tests

CI runs on every pull request and every push to `main`. It runs the send-list script's tests and `claude plugin validate plugins/crew`, and needs no Crew or Anthropic sign-in; the Claude Code version it uses is pinned in [`.github/ci/package.json`](.github/ci/package.json). `claude plugin validate` fails on a malformed `plugin.json`, one with no `name`, or a `hooks/hooks.json` that isn't valid JSON. It reads each skill's frontmatter but only warns, so an empty `SKILL.md` still passes. It doesn't check that a hook's script exists, and CI doesn't validate the marketplace's plugin source. To run the tests from your clone:

```bash
python3 -I plugins/crew/skills/send-list/scripts/test_send_leads.py -v
```

## License

[MIT](LICENSE)
