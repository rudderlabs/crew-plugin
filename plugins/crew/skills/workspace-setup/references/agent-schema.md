# Agent schema

Where each part of a Crew agent lives in the body, what turning it on checks, and how to find out when this file has drifted.

**The server is the source of truth.** `agent_bodySchema` returns the current JSON Schema plus the cross-field rules the schema can't express. Call it at the start of every authoring session; where it disagrees with this file, trust it and tell the user, because it usually means the product moved. This file was written from a live `agent_bodySchema` read and the server's own code.

## Contents

- [Discovering schema](#discovering-schema)
- [Body map](#body-map)
- [Where the Act lives](#where-the-act-lives)
- [Runtime state, drafts and publishing](#runtime-state-drafts-and-publishing)
- [What turning an agent on checks](#what-turning-an-agent-on-checks)
- [Tools in Shadow and dry runs](#tools-in-shadow-and-dry-runs)
- [What a person says publicly: an enrichment, not a tool](#what-a-person-says-publicly-an-enrichment-not-a-tool)
- [Retired and decoy fields](#retired-and-decoy-fields)
- [Failure modes](#failure-modes)

## Discovering schema

1. **`agent_bodySchema`** — the shape and the invariants in one call. Read the invariants; they are the expensive lessons.
2. **`context_get`, `catalog_list`, `channels_list`, `mcp_listTools`, `enrichment_list`** — the exact values a body refers to (event names, channel ids, tool names, enrichment ids). None of these can be guessed from outside, and a wrong one usually fails silently rather than loudly. `enrichment_list` works for anyone who can read Agents; `enrichment_preview` and a person's results also need `users:read` (`mcp-map.md`).
3. **Read back after every save** (`agent_get`, or `draft_get` for a draft), and run `scripts/check_body.py` on what came back. The API normalizes and drops unrecognized fields, so a 200 does not mean everything was stored. The fields that vanished are fields that don't exist, which is information.
4. **Copy an existing agent** when the workspace has one that works: `agent_get` on it shows a complete, valid body in this workspace's conventions.

If a relationship still can't be established after that, stop guessing. Write down what was tried, what the read-back showed and the exact error, and hand it to whoever owns the service.

## Body map

The fields that matter for authoring, grouped by ODA layer. Limits are character caps enforced on write.

```
skillId, displayName          identity; skillId is the stable key
version                       body.version = the published content version (see below)
priority                      lower runs first when several agents match one event
triggers[]                    { eventName, when? }  — the processing gate; names from catalog_list
successEvent[]                { eventName, when? }  — the outcome that counts as a win
attributionWindowDays         1–30
goal                          ≤2000, the outcome the agent is moving

OBSERVE
skills[]                      { skillId, name, promptFragment ≤4000 }  — one per signal
enrichmentIds[], agentToolNames[], webAccess   Shadow refuses tools it can't classify as reads (see below)
agentPrompt                   ≤10000, preamble for the reasoning phases (see note)

DECIDE  (decisionLogic)
strategy                      "policy_constrained_llm_selection" (the only value)
hardConstraints[]             { condition, effect }  — kill switches, not preferences
acts[]                        { id, name }  — a bundle of actions
options[]                     { id, name, whenToPrefer ≤2000, actId }  — when this fits → which act
actionPolicies[]              { id, actId, action, eligibility?, channelId | channelType, destinationId? }
whenNoClearFit                "hold_off" (default) | "closest_action"
priorityGuidance              ≤2000

ACT
availableActions[]            { id, type, enabled, channel, sender?, payloadTemplate? , channel fields }
brandVoice                    ≤2000, voice rules for every message this agent writes
followUp                      { enabled, count 1–10, gapDays 1–30, guidance ≤2000, decideGuidance }
guardrails                    { deduplicationWindow "72h", maxActionsPerEntityPerDay, …PerWeek }
scheduling                    { triggerDelay "0s" }
notifyChannel                 { channelId }
```

Note on `agentPrompt`: its schema comment says it reaches Act content generation, but it does not reach the message writer. Put voice rules in `brandVoice` and per-action rules in the message instructions, never only in `agentPrompt`.

## Where the Act lives

An action is split across two arrays, joined by `id`:

|            | `decisionLogic.actionPolicies[]`                                           | `availableActions[]`                                                                |
| ---------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Holds      | routing: which act owns it, which channel, Decide's per-action eligibility | content: who it's from, what to write, which fields                                 |
| Key fields | `id`, `actId`, `action` (display name), `channelId` or `channelType`       | `id` (same as the policy's), `type` (same as `action`), `sender`, `payloadTemplate` |

**The message instructions are `availableActions[].payloadTemplate.prompt`** (1–10,000 characters). This is the "Message instructions" box in the UI editor. Its siblings:

- `payloadTemplate.outputFields` — the names of the fields the writer fills, e.g. `["subject", "body"]` for email, `["message"]` for SMS or Slack. Names only: there is nowhere to describe a field, so say what goes in each field inside the instructions. With none set, the writer falls back to `subject` and `body`. A templated channel (Customer.io Design Studio, CleverTap, Braze) supplies its own fields from the template instead. The name also sets the field's format: `subject`, `subject_line`, `preheader` and `preview_text` are plain text, and every other name, Slack's `message` included, is HTML to the writer. `act-writing.md` → "Say each field's format".
- `sender` — `{ name, title, email }`, all three required when present. The writer sees name and title; Customer.io needs the email as the From address.

**Use one id for both halves.** Give every policy an explicit `id`, and give its `availableActions[]` entry the _identical_ `id` and `type == action`. The harness finds an action's instructions by the policy's `id`, and so does the editor. A natural-looking split such as policy `id: "policy-winback"` with `availableActions` `id: "winback_email"` orphans the instructions: the editor shows an empty Message instructions box, the harness generates nothing, and no validation refuses it. The same happens with no `availableActions[]` entry at all, or one with no `payloadTemplate`. How to write the instructions themselves is in `act-writing.md`.

The chain from Decide to Act is: an **option** (`actId`) → an **act** → the **action policies** that carry that `actId`. Several options may share one act. Every act must own at least one action or the body is refused.

## Runtime state, drafts and publishing

An agent's runtime state is one value on the agent row: **Off**, **Shadow** or **Live**.

- `off` — not evaluating. `agent_create` always creates the agent Off, and an Off body is parsed leniently, so a half-built agent saves. Over MCP the server stores the created agent's mode as Shadow whatever the body says (the `neverLive` pin), so resuming it from the Agents list starts it in Shadow; going Live is a human step in the editor. Send `launchMode: "shadow"` anyway, so the body says what it will run as.
- `shadow` — decides on real events, every send suppressed, **Slack posts included**. Drafts are reviewed on the Decisions page, not in the Slack channel the action targets; tell the user so when the action is a Slack post for a human to review. Tools that don't classify as reads are refused too, so a Shadow decision can rest on less than a Live one would ([below](#tools-in-shadow-and-dry-runs)). Reached with `agent_update { skillId, version, status: "shadow" }`; that call carries no body.
- `live` — decides and sends. Refused over MCP: a person turns an agent Live in the UI.

The body mirrors the state as `launchMode` (`shadow` | `live`) and `isActive`. Publishing re-stamps both from the row, so a body you write can't change the runtime state. A draft body must carry `launchMode` `shadow` or `live`, never `off`.

**Drafts.** Editing a published agent goes through a server draft: `draft_createForSkill { skillId, version, body, expectedPublishedVersion }`, then `draft_save { draftId, body, expectedRevision }`. Keep the returned `draftId`. Nothing written to a draft reaches production until it is published: with `draft_publish` where the server has it, otherwise by a person in the UI ("Publish vN+1" on `/agents/<skillId>@<version>`).

**The working copy may be the user's.** A published Agent has one working copy, the one the app's editor shows, and `draft_save` replaces it whole; `draft_getForSkill` shows whether one exists. If the user is editing the Agent in the app, don't save to it: copy the Agent into a separate working copy with `draft_createFromSkill`, dry-run that copy by its `draftId`, and give the user the changed fields to paste. Never `draft_publish` the copy, which would make it a new Agent; `draft_discard` it when done.

**Publishing over MCP.** `draft_publish` publishes a draft for an agent that isn't Live. After a publish, read the Agent back with `agent_get` and check that `body.version` went up before telling the user it is published: a refused call can look like a finished one. An older server may not have it, so check `tools/list` on the server you are using. Where it is missing, there is one other MCP-only way to ship a body: `agent_create` stores the body it is given as the published version 1, and the agent lands Off. So a new body can go out as a fresh agent: create it, read it back, run `check_body.py`, move it to Shadow with `agent_update`, and turn the agent it replaces Off. Two things to know:

- **Action ids another agent already uses are re-minted.** In one workspace, `<brand>_welcome_email` came back as `welcome_email_<brand>s`. Both halves (the policy and its `availableActions[]` entry) get the same new id, so nothing is orphaned, but anything that scripts against the old id breaks. Read the ids from the read-back.
- **It is a new agent, not a new version.** It starts with no decisions, no history and its own Decisions filter. For a change to an agent already running, publish its draft instead.

**Two version numbers.** The top-level `version` on `agent_get` locates the row and never moves. `body.version` is the published content version and goes up on every publish; `expectedPublishedVersion` takes this one.

## What turning an agent on checks

`agent_update` to Shadow re-validates the stored body strictly. A body that saved fine can be refused here; the error names the field path. Checks, roughly in the order people hit them:

- **Every option links to an act** (`options[].actId` names an existing `acts[].id`), and **every act owns at least one action**.
- **Channel binding.** Shadow accepts a bare `channelType` (a cold start, no channel picked yet). Live needs a real 27-character `channelId` on every action and rejects `channelType`. So Shadow → Live can be refused; Live → Shadow never is.
- **Message instructions** are required for actions on Customer.io, CleverTap (when the campaign has authored keys), Twilio and Braze. **Slack and webhook actions are not checked**, so check them yourself: a Slack action that posts a draft for a human needs instructions as much as an email does.
- **Send gaps** for a bound channel: Customer.io needs a Design Studio template and a complete sender; CleverTap and Braze need a campaign.
- **Follow-up:** `gapDays` must be within `attributionWindowDays`.
- **Enrichments** named in `enrichmentIds` must exist and be enabled, and the workspace must have Profile enrichment, a feature the RudderStack team enables on request. Without it, leave `enrichmentIds` out and the Agent turns on.
- **Not checked: whether the agent's tools will run.** An agent whose `agentToolNames` Shadow refuses turns on without a word. Check it yourself after the first decision ([next section](#tools-in-shadow-and-dry-runs)).

## Tools in Shadow and dry runs

**What happened.** An agent that wrote to people about their public views read each person's latest posts with two agent tools, `Twitter_MCP__get_user_last_tweets` and Apify's `harvestapi--linkedin-profile-posts`. Both would run Live. In Shadow both were refused on every decision. The model got an error string and decided anyway, and nothing on the Agent page said so. Only `analytics_getExecution` showed it.

One gate sits in front of every tool call:

| Mode                                                        | A tool runs when                                                                 |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Live                                                        | always                                                                           |
| Shadow                                                      | its effect classifies as `read`                                                  |
| Dry run (`preview_tryEvent`, replays, the editor's Dry Run) | its server declares `readOnlyHint: true` **and** its effect classifies as `read` |

**How a tool is classified.** Crew reads the tool's name, its description and the server's annotations, and keeps the most severe reading:

- A write verb anywhere in the name or the description (`add`, `create`, `send`, `set`, `update` and more) makes it a write, even when the server says `readOnlyHint: true`.
- A destructive verb (`delete`, `remove` and more), or `destructiveHint: true`, makes it destructive.
- A name and description with no verb the classifier knows give `unknown`, even with `readOnlyHint: true`, and `unknown` is refused. A read verb (`get`, `list`, `search`, `fetch` and more) is what makes a tool a read.

The two tools from that agent:

| Tool                                                             | Server says                                  | Classified                                                                        | In Shadow |
| ---------------------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------------- | --------- |
| `Twitter_MCP__get_user_last_tweets`                              | `readOnlyHint: true`                         | write: its description says "Set includeReplies=true…", and `set` is a write verb | refused   |
| `Apify_Linkedin_Integration__harvestapi--linkedin-profile-posts` | `destructiveHint: true` (Apify's annotation) | destructive                                                                       | refused   |

**The refusal is quiet.** The model reads "Error: tool <name> was not run because this is a shadow run…" and carries on with what it has. The decision lands, usually with a signal that couldn't find what the tool would have returned. Nothing on the Agent page shows it. And the UI tool picker's **Select read-only** looks only at the server's `readOnlyHint` and `destructiveHint`, so it selects `get_user_last_tweets` along with the real reads.

**Check, don't assume.** This rule is being worked on, so verify each agent rather than trusting a list:

1. **Before building:** `mcp_listTools`, and read each bound tool's `enrichmentReadAllowed`. It is the dry-run gate's own answer. `true` means the tool runs in a dry run and in Shadow. `false` means a dry run refuses it and Shadow may too; both tools above were `false`.
2. **After the first Shadow decision:** `analytics_getExecution {decisionId}`. Every entry in `calls[]` should be `ok: true`. A refused call has `ok: false` and an `errorText` containing "was not run because this is a shadow run".
3. **When a tool is refused,** get the fact another way, usually a research enrichment ([next section](#what-a-person-says-publicly-an-enrichment-not-a-tool)), or drop the tool. Don't leave a refused tool bound: the Shadow period then measures an agent that decides on less than the one going Live.

## What a person says publicly: an enrichment, not a tool

**What happened.** With the post-reading tools refused in Shadow, the same agent got each person's public voice from a research enrichment instead, and it worked in every mode.

Why an enrichment is the right home for it:

- It runs before Observe, on tools that are `enrichmentReadAllowed` (an enrichment may call no others), so Live, Shadow and a dry run see the same facts. `preview_tryEvent` acquires a result the person is missing and keeps it, as Live does; a made-up `userId` has nothing to enrich.
- Its result is in the snapshot the decider, the writer and the judge all read, so its facts are on the record. A fact a tool found in Observe isn't, until a signal restates it.
- It is cached per person and shared by every agent that names it.

The definition that worked, with the brand and topic as placeholders. Creating it needs `skills:write` and the workspace's Profile enrichment feature (the RudderStack team enables it on request); previewing it also needs `users:read`:

```json
{
  "name": "<Brand> · Public voice",
  "method": "research",
  "enabled": true,
  "config": {
    "cardinality": "one",
    "maxToolCalls": 5,
    "allowedTools": [
      { "kind": "builtin", "toolName": "web_search" },
      { "connectionId": "<Tavily connection id from mcp_listTools>", "toolName": "Tavily_MCP__tavily_search" }
    ],
    "bindings": [
      { "name": "first_name", "required": true, "source": { "kind": "trait", "path": "firstName" } },
      { "name": "last_name", "required": true, "source": { "kind": "trait", "path": "lastName" } },
      { "name": "company", "required": false, "source": { "kind": "trait", "path": "company" } }
    ],
    "brief": "Find what this person has said in public in the last 12 months about <topic>. Search for first_name last_name with the company: their posts on X and LinkedIn as indexed, interviews, podcasts, talks, the company blog. Accept a source only when it is clearly this person at this company; a namesake is not them. Summarise in your own words, naming the site each point came from. Report nothing when nothing public ties to them. Work facts only.",
    "outputs": [
      {
        "key": "ai_stance",
        "label": "Public stance on <topic>",
        "type": "text",
        "maxChars": 300,
        "description": "One or two sentences in your own words, ending with the site it came from in brackets."
      },
      {
        "key": "team_expectation",
        "label": "What they expect of their teams",
        "type": "text",
        "maxChars": 300,
        "description": "What they have said they expect of their people on <topic>, with the site in brackets. Empty when nothing."
      },
      {
        "key": "ai_themes",
        "label": "Themes",
        "type": "text_list",
        "description": "Up to three short themes they return to."
      },
      {
        "key": "sources",
        "label": "Sources",
        "type": "text_list",
        "description": "The sites the points came from, domain only."
      }
    ]
  }
}
```

**For their actual posts, copy, never reword.** A research value survives only if each excerpt it cites appears verbatim in a tool result the research read; otherwise it is dropped and the result's error says `Unsupported factual evidence for: <field>`. An output meant to hold a person's post must therefore be the post exactly as the tool returned it, with its link and date in separate outputs; the first version wrapped each post with its month and link, and every post was dropped. The recipe that worked for X posts, as a second research enrichment:

- **Tools:** `web_search`, a Tavily search tool, `Twitter_MCP__get_user_info` and `Twitter_MCP__get_tweets_by_ids` (a read that runs in Shadow, unlike the timeline tools); `maxToolCalls: 10`.
- **Brief:** take the X handle from the person's other results, confirmed with `get_user_info`; search for `x.com/<handle>/status/` URLs on the topic; take the numeric ids from those URLs and call `get_tweets_by_ids` with up to ten; report only posts it returned whose author is this person, not retweets; "copy post text exactly as the tool returned it; never reword it".
- **Outputs, kept apart:** `x_posts` (`text_list`, each post's text exactly as returned), `x_post_links` and `x_post_dates` in the same order, and a one-sentence `posting_themes` in the model's own words.

Like any research it resolves on some runs and not others. Refresh a person once or twice when a run failed, or after you correct an input (the handle, the brief); each refresh is a new acquisition and costs calls. A person with no public or indexed posts has none to find, and an empty result is then the right answer.

In the public-voice definition above, each value is a summary that ends with its site, not a quote. A summary can't be pasted into an email as the person's words, and the site lets an internal brief name its source. Then set `agentToolNames: []` and say so in Observe ("You have no tools: everything public is already in PROFILE ENRICHMENTS"), so the model doesn't go looking.

## Retired and decoy fields

Don't write these; each one has misled an author before.

| Field                                                       | Why not                                                                                                                                                                                                                           |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `decisionLogic.actionPolicies[].payloadTemplate` (a string) | **Looks like the message prompt and isn't.** It's a legacy pass-through that no dispatcher reads. Writing the instructions here leaves the real box empty and generates nothing. Use `availableActions[].payloadTemplate.prompt`. |
| `decisionLogic.actionPolicies[].shadow`                     | Retired. Shadow is the agent's runtime state now, set with `agent_update`. Still parsed for old version snapshots.                                                                                                                |
| `status: draft \| active \| paused` in a body               | The old state model. The states are `off`, `shadow`, `live`, and they live on the row.                                                                                                                                            |
| Duration strings in `followUp.gapDays`                      | It's an integer number of days.                                                                                                                                                                                                   |

## Failure modes

| Error                                                                                                                 | Meaning                                                                                                                                                                                        |
| --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Validation failed at 'X': expected <type>, received undefined`                                                       | Required field missing. Check `agent_bodySchema` rather than iterating field by field.                                                                                                         |
| `Invalid option: expected one of A\|B\|C`                                                                             | Enum. Use a listed value.                                                                                                                                                                      |
| `- decisionLogic.actionPolicies.0.channelId: …`                                                                       | Field-path error, usually from turning an agent on. Fix that field.                                                                                                                            |
| `Option "<name>" is not linked to an Act`                                                                             | `options[].actId` missing or names no act.                                                                                                                                                     |
| An act with no actions is refused                                                                                     | Give it a policy with the act's `actId`, or remove the act.                                                                                                                                    |
| Write succeeds with a warning naming a tool                                                                           | `agentToolNames` entry doesn't match `mcp_listTools`; the harness will drop it silently at decision time.                                                                                      |
| Shadow decisions land, but `analytics_getExecution` shows `ok: false` with "was not run because this is a shadow run" | The tool doesn't classify as a read. Nothing on the Agent page shows it. See [Tools in Shadow and dry runs](#tools-in-shadow-and-dry-runs).                                                    |
| Action ids differ from the body you sent to `agent_create`                                                            | Another agent in the workspace already uses them, so they were re-minted on both halves. Use the ids from the read-back.                                                                       |
| `FORBIDDEN: Missing permission: users:read` on an `enrichment_*` or `users_*` tool                                    | The caller lacks `users:read`: over the OAuth sign-in, the user's role; on a personal access token, the opt-in `people` scope. Not a schema problem; see `mcp-map.md`.                         |
| Agent runs, decisions show, drafts are empty; the editor's Message instructions box is empty though the body has text | The policy's `id` and its `availableActions[]` entry's `id` differ, so the instructions are orphaned. Or there's no `payloadTemplate.prompt`, or the text went into the policy's decoy string. |
| `FORBIDDEN: Missing permission`                                                                                       | Permission gate — see `mcp-map.md`. Not a schema problem.                                                                                                                                      |
