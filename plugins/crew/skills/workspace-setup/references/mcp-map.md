# MCP capability map

What the relevant MCPs can do, what they can't, and how to reason when something is missing.

Treat the specifics below as **observed at a point in time, not guaranteed**. Permissions differ per token, per workspace, and per user. Capabilities get added. Always let an actual tool response override this document — and when it does, that's worth telling the user, because it usually means either a scope change or a product change.

## Contents

- [Signing in and permissions](#signing-in-and-permissions)
- [Crew MCP](#crew-mcp)
- [What only the Crew team can turn on](#what-only-the-crew-team-can-turn-on)
- [RudderStack MCP](#rudderstack-mcp)
- [Optional context sources](#optional-context-sources)
- [Reasoning about gaps](#reasoning-about-gaps)
- [The paste-ready artifact pattern](#the-paste-ready-artifact-pattern)

## Signing in and permissions

**The sign-in picks the workspace.** The plugin's Crew server signs in with OAuth (in Claude Code: `/mcp`, the Crew server, Authenticate). Someone who belongs to several workspaces chooses one while signing in, and every tool then works in that one; no tool takes a workspace parameter. Confirm which workspace is connected before writing anything (`context_get` returns its name): writing a customer's agent into the wrong workspace is an expensive mistake. To switch, clear the Crew server's authentication in `/mcp` and sign in again.

**Over the sign-in, Claude has the user's role, nothing more.** Crew reads the role itself rather than from the token, so a role change applies within minutes, without signing in again. The two roles:

| Role     | Holds                                                                                                 | Cannot                                                      |
| -------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `member` | Every read, plus Agent, channel, catalog, MCP-connection and webhook writes                           | Save the Context page, rename the workspace, manage members |
| `admin`  | Everything `member` holds, plus `workspace:manage` (Context, workspace settings) and `members:manage` | —                                                           |

An invited person joins as `member`; an admin promotes them under Settings → Members. The roles are configured outside the app and can grow, so a tool's own `FORBIDDEN: Missing permission: <slug>` is the authority on what the current role lacks.

**A personal access token carries a scope instead of a role.** Tokens (Settings → MCP → Access tokens) are for scripts and clients without OAuth. Each is minted in one workspace and stays there:

| Scope     | Adds                                                                                                                                   |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `read`    | Agent, decision, catalog and channel reads                                                                                             |
| `write`   | Agent writes, dry runs and Calibrate                                                                                                   |
| `people`  | Everything `write` has, plus people and enrichment results (`users_*`, `enrichment_preview`, ...), API connections and `webhooks_list` |
| `setup`   | Everything `people` has, plus `webhooks_create`                                                                                        |
| `reviews` | Reads, the decision actions (approve, edit and send, reject), and people reads; no Agent or webhook writes                             |

## Crew MCP

Tool groups (`tools/list` is the live answer):

| Group                              | What it does                                                                                                                                                                                                                                    | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent_*`                          | `bodySchema`, `list`, `get`, `create`, `update`, `rename`, `delete`, `listVersions`, `getVersion`, `checkRestore`                                                                                                                               | `bodySchema` first. `create` lands the agent **Off** and stores its body as the published version 1; action ids another agent uses are re-minted. `update` changes runtime state only (Off ↔ Shadow, no body); `live` is refused.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `draft_*`                          | `createForSkill`, `createNew`, `createFromSkill`, `get`, `getForSkill`, `save`, `list`, `discard`, `replaceFromVersion`, `publish`                                                                                                              | The working copy of a published agent. Saves are revision-checked. `draft_publish` publishes a draft onto an agent that is Off or Shadow, and never changes its runtime state; a Live agent is refused, and a person publishes onto it in the app.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `preview_*`                        | `tryEvent` (synchronous dry run on a synthetic event, or on a list of up to 10 at once with one answer each: always a list for several people or events), `start` / `get` (replay recent decisions against a draft), `listRecent`               | How you see generated drafts before anything runs. `tryEvent` needs no webhook and no past decisions; `start` needs decisions the agent already made. Both cost money: they run the agent's read-only tools for real (a tool that does not declare itself read-only is refused) and can fetch and cache enrichment results; only the send is suppressed, and no decision is stored. `tryEvent` can time out on research-heavy agents. `tryEvent` with `followUpOf: <a delivered decision id>` in place of `event` rehearses the agent's NEXT follow-up after that message (Live or Shadow), standing the follow-up gap later with the person's history as of then — the way to read follow-up guidance before going Live.                 |
| `analytics_*`                      | `list` and `get` (decisions with signals, rationale, judge verdict and generated content), `getAnalytics` (aggregates), `getExecution` (every tool call behind one decision, with `ok` and `errorText`), `getLineage`, `getSkillVersionMetrics` | Pass every outcome to count everything; `pageSize` is 25, 50 or 100. `getExecution` is the only place a tool refused in Shadow shows up.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `context_get`                      | Workspace memory (workspace.md) and the workspace's name                                                                                                                                                                                        | Read-only here. Editing it is the Context page in the app, and saving needs the `admin` role.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `catalog_*`                        | Events the workspace actually receives, per webhook, with their property paths                                                                                                                                                                  | Read before writing triggers. Importing a catalog file, editing descriptions and marking a property as an identifier are on the Events page only.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `webhooks_create`, `webhooks_list` | Create an inbound webhook; list them                                                                                                                                                                                                            | `create` needs `webhooks:write` and answers with the webhook's `url` and bearer `token`, once: they cannot be read again over MCP, so save them where the user can reach them. `format: "rudderstack"` (the default) takes RudderStack calls as they are. `list` never returns a token. A webhook carries a `rudderstack` block only when Crew's own RudderStack link is on (below). Editing, revoking and revealing credentials stay in the app.                                                                                                                                                                                                                                                                                         |
| `channels_*`                       | Channel ids and types                                                                                                                                                                                                                           | Needed to bind an action for Live. Connecting a channel holds a credential, so it is done in the app.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `mcp_list`, `mcp_listTools`        | Tools an agent can use, with exact names                                                                                                                                                                                                        | Read before writing `agentToolNames`. Each tool's `enrichmentReadAllowed` is the dry-run gate's answer: `true` means it runs in a dry run and in Shadow; `false` means it may be refused there (`agent-schema.md` → "Tools in Shadow and dry runs").                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `enrichment_*`, `users_*`          | Profile enrichments; people                                                                                                                                                                                                                     | **A person's facts need `users:read`**: every `users_*` call, and `enrichment_preview`, `refresh`, `personResults` and `getGeneration`. It comes from the role over the sign-in, or from a token with the `people`, `setup` or `reviews` scope; a default `read` or `write` token answers `FORBIDDEN: Missing permission: users:read`. Listing, reading and writing enrichment definitions needs only an Agent or people permission (`skills:*` or `users:*`). `users_list` gives a person's `id`, which the enrichment tools take as `userPk`. `enrichment_preview` with `userPk` reuses that person's cached research (with `subject` it starts cold). A failed `enrichment_refresh` replaces the earlier result, good values included. |
| `apiconnections_*`                 | API connections                                                                                                                                                                                                                                 | `list` and `get` need `skills:write` or `apiconnections:write`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `accounts_list`, `accounts_get`    | Companies the workspace's people are grouped into (where accounts are on): ids, domains, people and the Agents that decided there                                                                                                               | Read-only, and need the opt-in `people` scope (`users:read`) like `users_*`. Every account write (merge, move, confirm, exclude a domain) stays in the UI. An account id scopes `analytics_getAnalytics` (`accounts`) and is the sample `enrichment_preview` takes (`accountId`) for an enrichment whose `subject` is `account`.                                                                                                                                                                                                                                                                                                                                                                                                          |
| `calibrate_*`                      | Agent Calibrate, round by round                                                                                                                                                                                                                 | The `calibrate` skill runs it. Publishes to Shadow only.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |

Not available over MCP, by design: creating a workspace or inviting people, turning an agent Live or publishing onto a Live one, writing workspace context, importing a catalog file or marking an identifier, connecting a channel, linking a RudderStack workspace, and anything else that handles a credential. There is no ingest tool either, but `webhooks_create` returns a URL and token Claude can post events to (`events-catalog.md` → "Test events from Claude Code"). For the rest, produce the artifact and hand it to the user.

**Shadow is the safe default for anything new.** A Shadow agent decides on real events and records its drafts without sending, which is what you want while the drafts are being reviewed. Moving it Live is a person's decision in the UI.

## What only the Crew team can turn on

Some capabilities are switched on per workspace by the Crew team and are not self-serve. None is needed to get an agent deciding in Shadow (`SKILL.md` → Stage 3 says when to raise them).

| Capability                                                                                                                                    | How to tell from Claude Code                                                                                                                                |
| --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Crew's own RudderStack link**: webhooks wired through a RudderStack instance Crew runs for the workspace, feeding a per-workspace warehouse | A webhook in `webhooks_list`, or the `webhooks_create` answer, carries a `rudderstack` block with a `wiringStatus`. No block: the link is off               |
| **Learning**: proposals that improve an agent from its outcomes, and warehouse-grounded workspace facts                                       | Not readable over MCP. Ask the Crew team                                                                                                                    |
| **Feature flags** such as profile enrichment and web search                                                                                   | Not readable either; a tool that needs one fails naming it (for example, external ids in a webhook mapping "require the workspace profile-enrichment flag") |

When the user needs one, say which and that their Crew contact turns it on; don't look for a way around it.

## RudderStack MCP

RudderStack's public MCP server (`https://mcp.rudderstack.com/mcp`, OAuth). It comes with RudderStack's `rudder-core` plugin (`/plugin marketplace add rudderlabs/rudder-agent-skills`, then `/plugin install rudder-core@rudder-agent-skills`), which signs in on first use; install it only that way, so there is one RudderStack server. It is the recon surface (`recon.md`) and the check that events leave RudderStack:

- **Reads:** sources (Reverse ETL sources too, with `list_sources` and `retl_type`), destinations and connections; each source's event names, schemas and properties; live events; per-destination event metrics and errors; Reverse ETL sync runs (`get_retl_source_syncs`) and the rows a run's destination refused (`get_retl_failed_records`).
- **Writes:** transformations: create or update one (`upsert_transformation`), test it on sample events before saving (`transformation_test_new`), and connect it to a destination.
- **Cannot:** create a source or a destination, connect one to the other, or start a Reverse ETL sync. Adding Crew's Webhook destination is the RudderStack app, Terraform or rudder-cli: the `connect-rudderstack` skill for event streams, the `connect-warehouse` skill for warehouse tables.

RudderStack also publishes agent skills for its own tools (the `rudderlabs/rudder-agent-skills` Claude Code marketplace: the MCP, Terraform, rudder-cli, tracking plans, Profiles). Use them for RudderStack mechanics; the skills here say what Crew needs.

OAuth expires. `invalid_grant` or a token-refresh failure means the connector needs reconnecting; that's a user action, not something to retry around. Ask, then retry once.

## Optional context sources

Never required, frequently valuable — they carry the customer's own framing rather than a reconstruction of it:

- **Call transcripts** (a meeting-notes MCP, for example). The strongest source for what the customer actually asked for, in their words and numbers. Prefer explicit listing over semantic search; proper nouns are often transcribed wrong.
- **Tickets** carrying use case, next steps, and named contacts. Status fields lag reality; treat them as weak signal.
- **Chat threads and wikis** — decisions and specs that never made it into a canonical doc.

When these are unavailable, proceed. A workspace built from recon plus the use case is perfectly serviceable; note which parts are unconfirmed.

## Reasoning about gaps

When an operation isn't available, diagnose before reacting. The three cases have different correct responses, and conflating them wastes time:

**1. Permission gate** — `FORBIDDEN`, `Missing permission: X`, `No approval received`.

The capability exists; this sign-in or token lacks it. Retrying is pointless. Do the operation in the UI instead, or with a role or token that has it. Then tell the user exactly which permission was missing, so their workspace admin or Crew contact can fix it once.

The common ones: `Missing permission: users:read` on a `users_*` tool or an enrichment tool that answers about a person, which on a token means it was minted without the `people` scope; and `Missing permission: webhooks:write` on `webhooks_create`, which on a token means it lacks the `setup` scope. Over the sign-in, either means the role lacks the slug: an admin changes the role.

**2. Expired auth** — `invalid_grant`, token refresh failure.

Ask the user to reconnect the connector. Retry once after they confirm. Don't build workarounds around a dead token.

**3. Missing capability** — no tool exists for the operation.

Ask in order:

- Is there an **adjacent primitive**? (No event-ingest tool, but `webhooks_create` returns a URL to post to. No bulk operation, but there's a single-item one that can be repeated.)
- Can the **UI** do it? Then produce the artifact and hand it over.
- Is it **actually needed**? Sometimes the missing capability was only required by an approach that has a simpler alternative.

Say which case you're in when reporting to the user. "The MCP can't write context: only an admin saves the Context page in the app — here's the block to paste" is far more useful than "that didn't work."

## The paste-ready artifact pattern

The universal fallback. When Claude can't write directly, produce something the user can paste in one action.

Good paste-ready artifacts:

- **Complete.** No placeholders to fill, no "add your fields here."
- **Correctly formatted** for the destination — markdown for a context page, JSON for a catalog field.
- **Delivered with a location.** "Paste this into Context (`/context`), save, then turn automatic updates off."
- **Free of commentary inside the block.** Notes go outside it, so the block can be copied wholesale.

This is often the right answer even when direct write is available — a customer-facing workspace generally benefits from a human reviewing before anything lands.
