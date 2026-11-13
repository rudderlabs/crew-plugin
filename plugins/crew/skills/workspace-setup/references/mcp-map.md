# MCP capability map

What the relevant MCPs can do, what they can't, and how to reason when something is missing.

Treat the specifics below as **observed at a point in time, not guaranteed**. Permissions differ per token, per workspace, and per user. Capabilities get added. Always let an actual tool response override this document — and when it does, that's worth telling the user, because it usually means either a scope change or a product change.

## Contents

- [Signing in and permissions](#signing-in-and-permissions)
- [Crew MCP](#crew-mcp)
- [Workspace features](#workspace-features)
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

**The session's own tool list wins.** This map names every Crew tool by its full name, grouped by what it works on, with what each tool's description leaves out. Where the tools this session lists differ from it (one missing, renamed or new), the list is right and the map is behind: say so to the user, because it means a role or scope change or a product change. A tool's own description and refusals outrank the notes here too. A tool missing from the list usually means the role or token lacks its permission.

### Agents

`agent_bodySchema`, `agent_list`, `agent_get`, `agent_create`, `agent_update`, `agent_rename`, `agent_delete`, `agent_listVersions`, `agent_getVersion`, `agent_checkRestore`

- `agent_bodySchema` first, every authoring session.
- `agent_create` stores the body as the published version 1; action ids another Agent already uses are re-minted on both halves. The state a new Agent starts in, and what `agent_update` can move it to: `agent-schema.md` → "Runtime state, drafts and publishing". `agent_update` carries no body.
- `agent_listVersions` and `agent_getVersion` read published releases; `agent_checkRestore` says what would stop one going back on, and `draft_replaceFromVersion` loads it into the working copy.
- `agent_delete` removes the Agent and its history for good: ask first.

### Drafts

`draft_createForSkill`, `draft_createNew`, `draft_createFromSkill`, `draft_get`, `draft_getForSkill`, `draft_list`, `draft_save`, `draft_discard`, `draft_replaceFromVersion`, `draft_publish`, `draft_convertToStrategy`

- The working copy of a published Agent. Saves are revision-checked.
- `draft_publish` publishes a working copy onto an Agent that is Off or Shadow and never changes its runtime state; a Live Agent is refused, and a person publishes onto it in the app.
- `draft_convertToStrategy` rewrites an Options Agent as a Decide-strategy working copy, with no model involved, and publishes nothing; it is refused where the workspace has no Decide strategies.

### Dry runs and replays

`preview_tryEvent`, `preview_start`, `preview_get`, `preview_listRecent`

- `preview_tryEvent` is a synchronous dry run on one event, or on a list of up to 10 with one answer each. For several people or events, always one call with a list. It needs no webhook and no past decisions, and can time out on research-heavy Agents. With `followUpOf: <a delivered decision id>` in place of `event` it rehearses the Agent's next follow-up after that message (Live or Shadow), standing the follow-up gap later with the person's history as of then: the way to read follow-up guidance before going Live.
- `preview_start` replays a draft against decisions the Agent already made, and `preview_get` reads the run; `preview_listRecent` lists recent runs.
- Both cost money. They run the Agent's read-only tools for real (a tool that does not declare itself read-only is refused) and can fetch and cache enrichment results; only the send is suppressed, and no decision is stored.

### Decisions

`analytics_list`, `analytics_get`, `analytics_getAnalytics`, `analytics_getExecution`, `analytics_getLineage`, `analytics_getSkillVersionMetrics`, and the decision actions `analytics_approve`, `analytics_editAndSend`, `analytics_reject`, `analytics_submitVerdict`, `analytics_saveFeedback`

- Reading: `analytics_list` and `analytics_get` are the decisions with their signals, rationale, judge verdict and generated content; `analytics_getAnalytics` the aggregates; `analytics_getExecution` every tool call behind one decision, with `ok` and `errorText`; `analytics_getLineage` the sequence a decision belongs to; `analytics_getSkillVersionMetrics` the outcomes per published version. Pass every outcome to count everything; `pageSize` is 25, 50 or 100. `analytics_getExecution` is the only place a tool refused in Shadow shows up.
- The decision actions need `decisions:write`: the role over the sign-in, or a token with the `reviews` scope. `analytics_approve` and `analytics_editAndSend` send a waiting message to a real person, on a Live Agent only: ask first, every time. `analytics_reject` sends nothing. `analytics_submitVerdict` reviews a decision as the Decisions page does, and a review is final; `analytics_saveFeedback` changes only its note.

### Workspace context and events

`context_get`, `catalog_list`, `catalog_get`, `webhooks_create`, `webhooks_list`

- `context_get` is the workspace memory (workspace.md) and the workspace's name. Read-only here: editing it is the Context page in the app, and saving needs the `admin` role.
- `catalog_list` and `catalog_get` are the events the workspace actually receives, per webhook, with their property paths. Read them before writing triggers. Importing a catalog file, editing descriptions and marking a property as an identifier are on the Events page only.
- `webhooks_create` needs `webhooks:write` and answers with the webhook's `url` and bearer `token`, once: they cannot be read again over MCP, so save them where the user can reach them (`events-catalog.md` → "Test events from Claude Code" has the file and the URL's shape). `format: "rudderstack"` (the default) takes RudderStack calls as they are. `webhooks_list` never returns a token. A webhook carries a `rudderstack` block only when Crew's own RudderStack link is on ([Workspace features](../../../README.md#workspace-features)). Editing, revoking and revealing credentials stay in the app.

### Channels

`channels_list`, `channels_get`, `channels_resources`, `channels_updateLimits`, `channels_setSenderDomain`

- `channels_list` gives each channel's id, type and recipient identifier: a Live action needs a real channel id. `channels_get` adds one channel's non-secret settings, its sender limits (`config.limits`) and, for a paced channel, its Live usage (`pacing`).
- `channels_list` and `channels_get` name, in `events`, what a channel reports back about its sends (a reply, a bounce, an accepted LinkedIn connection). Each is an event name for a trigger or a success event. It arrives for every Agent's sends on that channel, so an Agent that acts only on its own adds the condition `resolved_agent_id` = `@self` to that trigger or success event (`agent_bodySchema` has the rule).
- `channels_resources` lists what an action on a channel can pick: Slack conversations, Customer.io emails, WhatsApp templates, CleverTap, Braze and HeyReach campaigns, and on a LinkedIn account connected through Crew (`auth_method` `managed`) its LinkedIn actions. Copy an item's `bind.fields` unchanged onto the action (`bind.on` `action`) or its action policy (`policy`). An item that needs attention has no `bind`; its `detail` says what the user fixes in the app.
- `channels_updateLimits` sets one sender's limits and `channels_setSenderDomain` one domain's daily cap. Both need `channels:write`, which only a role over the sign-in holds (no token scope grants it). Ask first: raising a limit can release messages waiting on that sender.
- Connecting a channel holds a credential, so it is done in the app.

### Tools an Agent can call

`mcp_list`, `mcp_listTools`, `apiconnections_list`, `apiconnections_get`, `apiconnections_updateInputs`

- `mcp_listTools` gives every tool an Agent can bind, with its exact name for `agentToolNames`. Each tool's `enrichmentReadAllowed` is the dry-run gate's answer: `true` means it runs in a dry run and in Shadow; `false` means it may be refused there (`agent-schema.md` → "Tools in Shadow and dry runs"). `mcp_list` shows the outbound MCP connections and whether each grant still works.
- `apiconnections_list` and `apiconnections_get` need `skills:write` or `apiconnections:write`. `apiconnections_updateInputs` replaces a connection's declared inputs, needs `apiconnections:write`, and drops every cached result of every enrichment on that connection: ask first.

### People, enrichments and accounts

`users_list`, `users_get`, `enrichment_list`, `enrichment_get`, `enrichment_create`, `enrichment_update`, `enrichment_disable`, `enrichment_dependents`, `enrichment_preview`, `enrichment_refresh`, `enrichment_invalidate`, `enrichment_personResults`, `enrichment_getGeneration`, `enrichment_health`, `enrichment_suggestOutputs`, `accounts_list`, `accounts_get`

- **A person's facts need `users:read`**: `users_list`, `users_get`, `enrichment_preview`, `enrichment_refresh`, `enrichment_personResults`, `enrichment_getGeneration`, `accounts_list` and `accounts_get`. It comes from the role over the sign-in, or from a token with the `people`, `setup` or `reviews` scope; a default `read` or `write` token answers `FORBIDDEN: Missing permission: users:read`. Reading and writing enrichment definitions needs only an Agent or people permission (`skills:*` or `users:*`).
- `users_list` gives a person's `id`, which the enrichment tools take as `userPk`. `enrichment_preview` with `userPk` reuses that person's cached research (with `subject` it starts cold). A failed `enrichment_refresh` replaces the earlier result, good values included; `enrichment_invalidate` only marks it stale.
- `enrichment_update` and `enrichment_disable` reach every Live Agent that names the enrichment at its next event, with no publish step: ask first, and read `enrichment_dependents` to say which Agents. `enrichment_health` shows how each enrichment's lookups went; `enrichment_suggestOutputs` is a model call that proposes outputs from a brief.
- `accounts_list` and `accounts_get` are the companies the workspace's people are grouped into, where Accounts is on: ids, domains, people and the Agents that decided there. Read-only; every account write (merge, move, confirm, exclude a domain) stays in the app. An account id scopes `analytics_getAnalytics` (`accounts`) and is the sample `enrichment_preview` takes (`accountId`) for an enrichment whose `subject` is `account`.
- Profile enrichment and Accounts are workspace features: [Workspace features](../../../README.md#workspace-features).

### Calibrate

`calibrate_eligibility`, `calibrate_start`, `calibrate_get`, `calibrate_getCard`, `calibrate_answer`, `calibrate_apply`, `calibrate_applyAnyway`, `calibrate_removeChange`, `calibrate_markKnownGap`, `calibrate_discard`, `calibrate_publish`, `calibrate_listRounds`, `calibrate_liveGate`

- The `calibrate` skill runs a Calibrate round by round; `calibrate_publish` publishes to Shadow only. `calibrate_liveGate` says what would stop each action sending Live, for the person who takes the Agent Live.

### Not over MCP

By design: creating a workspace or inviting people, turning an Agent Live or publishing onto a Live one, writing workspace context, importing a catalog file or marking an identifier, connecting a channel, linking a RudderStack workspace, changing a workspace feature, and anything else that handles a credential. There is no ingest tool either, but `webhooks_create` returns a URL and token Claude can post events to (`events-catalog.md` → "Test events from Claude Code"). For the rest, produce the artifact and hand it to the user.

**Shadow is the safe default for anything new.** A Shadow Agent decides on real events and records its drafts without sending, which is what you want while the drafts are being reviewed. Moving it Live is a person's decision in the app.

## Workspace features

Some capabilities are switched per workspace and are not self-serve: Profile enrichment, the built-in web tools, the HeyReach channel, Crew's own RudderStack link, learning and more. The plugin README's [Workspace features](../../../README.md#workspace-features) table lists each one, whether a new workspace has it, and how to tell from Claude whether it is on. When the user needs one that is off, name it and say who changes it, as that table does; don't look for a way around it. None is needed to get an Agent deciding in Shadow (`SKILL.md` → Stage 3 says when to raise them).

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
