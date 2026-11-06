# The event catalog

The catalog is the vocabulary the agent's triggers and signals refer to. Event descriptions feed agent decisioning directly, so vague descriptions produce vague decisions.

## Contents

- [Deriving the catalog](#deriving-the-catalog)
- [Structure](#structure)
- [Getting events in](#getting-events-in)
- [Test events from Claude Code](#test-events-from-claude-code)
- [Events Crew refuses](#events-crew-refuses)
- [Webhook seeding gotchas](#webhook-seeding-gotchas)
- [Trigger name mismatch](#trigger-name-mismatch)

## Deriving the catalog

Two inputs: **recon** (what data actually exists) and **the use case** (what the agent needs to reason about). The catalog is the intersection, plus outcomes.

Include four categories, and don't skip the third:

1. **Trigger events** — what starts a decision.
2. **Signal events** — what the Observe layer reasons over. Engagement, behavior, state changes.
3. **Outcome events** — what tells you whether the decision was right. Both the success and the failure case.
4. **Entity traits** — identity and contactability attributes carried alongside.

**Outcome events are the ones most often forgotten and the most expensive to add late.** Without them there is no baseline, no measurement, and nothing for a learning loop to consume. In a shadow-mode deployment they're the _only_ thing that produces a usable metric — see `oda-design.md` → "Shadow mode".

## Structure

```json
{
  "identity": {
    "note": "How identity and traits arrive.",
    "traits": ["firstName", "email", "mobile", "consentFlag", "timezone"]
  },
  "events": [
    {
      "name": "thing_happened",
      "type": "track",
      "description": "One sharp sentence: what this represents and why it matters to a decision.",
      "properties": [
        { "name": "entityId", "type": "string" },
        { "name": "occurredAt", "type": "string", "description": "ISO 8601." }
      ]
    }
  ]
}
```

**Descriptions do work.** They're read during decisioning. "Prospect books a demo — primary trigger" is useful; "booking event" is not.

**Name events semantically, not structurally.** `demo_booked` beats `webhook_source_event`. The gap between those two is real work — see [trigger name mismatch](#trigger-name-mismatch).

## Getting events in

Four paths, in the order a new workspace usually needs them. Choose by purpose: _structure and reasoning_ need only a dry run or a pasted catalog; _decisions happening on their own_ need events flowing through a webhook.

| Path                                                    | Who does it                                                                   | Gives you                                                                                                                         |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **Dry run** with `preview_tryEvent`                     | Claude                                                                        | Decisions and drafts on events Claude writes, in one call, with no webhook and no decision stored                                 |
| **Pasted catalog** on the Events page (upload or paste) | The user, in the app                                                          | Descriptions before any event arrives; marked as file-sourced, and they outrank AI-drafted ones. Catalog import is not on the MCP |
| **Test events through a webhook**                       | Claude, with `webhooks_create` and `scripts/send_events.py`                   | Real Shadow decisions, people under Users, and a catalog built from what arrived                                                  |
| **Real events** from the customer's RudderStack         | The user adds a Webhook destination; the `connect-rudderstack` skill walks it | Live traffic. Warehouse rows go through Reverse ETL: the `send-list` skill's `references/recurring-sync.md`                       |

There is no ingest tool on the Crew MCP, but `webhooks_create` returns the webhook's URL and bearer token, so Claude can post events itself. `catalog_list` reads back what the workspace has actually received: it is the check that events arrived and the source of exact names for triggers.

## Test events from Claude Code

**Dry-run first.** `preview_tryEvent` runs an Agent (published, by `skillId` and `version`, or a working copy, by `draftId`) on up to 10 events in one call and answers each one, `fired` first. It needs no webhook, so it is the way to test an Agent that has never fired, and to try the same people again after every edit. A made-up person has no profile, so whatever the Agent needs to know about them (name, plan, company) goes in the event's `properties`, and their email in `identifiers`; `send_events.py --try-event` does that from a test-events file. A dry run sends nothing and stores no decision, but an id that matches a real person reads their profile, and a missing enrichment result is fetched and kept as production would, spending real money. Use fictional people.

**Then send through a webhook, for what a dry run cannot give:** Shadow decisions on the Decisions page, real events for Calibrate to replay, and a catalog built from real arrivals. Send the ones meant to produce decisions once the Agent is in Shadow: Crew decides on an event only for the Agents that are on when it arrives, and never replays it later, so events sent to an Off Agent leave the Decisions page empty. A check that only proves a new webhook's token works (`connect-rudderstack` sends one identify and one track on an event name no Agent triggers on) can go any time. Each step below changes the workspace, so get the user's yes first.

1. `webhooks_create` with `format: "rudderstack"` and a name for what it carries (`Test events`). It needs `webhooks:write`: an admin or member role over the sign-in, or a personal access token with the `setup` scope. It answers with `url` and `token`, once; neither can be read again over MCP, and only the Crew app can revoke the webhook.
2. Save both in `~/crew-lists/webhooks/<webhookId>.env`, where the plugin's scripts look: create it with `mkdir -p -m 700 ~/crew-lists/webhooks && install -m 600 /dev/null ~/crew-lists/webhooks/<webhookId>.env`, then fill it with the Write tool as `CREW_WEBHOOK_URL=...` and `CREW_WEBHOOK_TOKEN=...`. Never `echo` it, print it, commit it or repeat the token in chat. The token also stays in the session transcript; if it leaks, create a new webhook and revoke the old one in the app.
3. Write the events as a JSON list of RudderStack calls, in a file outside the repository: an `identify` per person (`userId` starting `crew-test-`, `traits` with a name and an `@example.com` email) and the `track` calls the Agent triggers on. Never a real person's id or address: an identify overwrites that profile.
4. Check, then send: `python3 <skill dir>/scripts/send_events.py --env ~/crew-lists/webhooks/<webhookId>.env --file events.json --run <label>`. The script refuses anything Crew would answer with a 400, sends identifies first, stamps each call with the time it is sent, refuses redirects (which would carry the token elsewhere), and prints one line per call. `--check` shows the first call without sending.

**Every identify arrives as the event `identify`, every page view as `page`.** A Live Agent that triggers on one of those names, or on a test event's name, decides on the test person for real and can message them. Check `agent_list` first; if any Live Agent would match, send none of those calls without the user's yes.

**Sending the same file again is ignored.** Crew deduplicates on the workspace and the `messageId`, even for events no Agent matched, and the script builds each `messageId` from `--run`, the call's place in the file and its content. To send the same people again (for example ones first sent while the Agent was Off), pass a new `--run`; the script exits 1 when every call came back a duplicate.

**A person keeps their history.** Every decision reads the person's earlier decisions, Shadow ones included, and so does a dry run on an existing person. Test people sent again after a change arrive with those decisions behind them, so a rule about how often to message someone can hold them: in one build, the same test people sent again after each fix were held by the Agent's own frequency rule. To test a change, use new test people (new `userId`s and emails), not only a new `--run`.

## Events Crew refuses

A RudderStack-format webhook answers these with a 400 and keeps nothing. A RudderStack Webhook destination drops a 400 or 401 without retrying (it retries 429 and 5xx), so from a live pipeline the event is simply lost:

- **An event name with any character other than letters, digits, spaces and `_ : . / -`** (parentheses, `&`, `'`, emoji, a newline), or longer than 512 characters.
- **A `userId` or `anonymousId` that is a number.** Send it as text.
- **An `originalTimestamp` with no time zone.** `2026-11-04T09:00:00` is refused; `2026-11-04T09:00:00Z` and `+01:00` are accepted (an offset is converted to UTC).
- **No `messageId`**, or neither a `userId` nor an `anonymousId`.

A `group` or `alias` call with no `event` is not refused but ignored (`202 ignored`); account facts belong on a track event (`account-agents.md`).

## Webhook seeding gotchas

Observed constraints when POSTing to the Crew webhook. Violating these produces silent no-ops more often than errors, which makes them expensive to debug:

- **Every track call needs an `event` string field.** Missing it is rejected.
- **Seed a profile with an identify call, before the track calls.** A RudderStack-format webhook accepts an identify with no `event`, and its traits (name, email, phone and any others) are what the person's profile keeps. A track call's `context.traits` are never read: ingest strips them before the harness runs, so names and contact details sent only there are lost, and the recipient cannot be resolved.
- **A new event's first arrivals can have no recipient.** Crew marks a property such as `properties.email` as an identifier in a background pass after an event name first arrives, so the first track events on a new webhook are decided before that mark exists. Seen in a Reverse ETL test run: the first event arrived with no email identifier, and a Customer.io send for it would have failed with no recipient. An identify before the first track avoids it, because the profile email does not depend on the mark; otherwise send one test row, then check with `catalog_get` that `properties.email` on that event has the role `identifier` (if not, the user marks it on the Events page; marking is not on the MCP).
- **The timestamp places the event; nothing is refused for its age.** `originalTimestamp` sets where the event sits in the person's session window and when a success event counts. An event older than that window (15 minutes until one of the person's events matches a trigger, then 15 days) is trimmed as it lands. For a live demonstration with made-up events, stamp them now. When replaying real historical events, keep their timestamps (`send_events.py --keep-timestamps`): restamping a real outcome moves it into a different attribution window.
- **A 2xx response does not mean the event was acted on.** `202 accepted` means stored; `200 duplicate` means the `messageId` was seen before. Whether an Agent decided shows in `analytics_list`, not in the response.

## Trigger name mismatch

The most common reason a correctly-built workspace produces zero decisions.

Raw sources deliver generic event names. Agents trigger on semantic names. If nothing bridges them, the trigger never matches — and every layer looks healthy: source has volume, destination reports delivered, no errors anywhere.

Bridging options:

- **A transformation on the destination** — maps raw payload to semantic event names and properties.
- **Producer-side mapping** — the upstream system sends semantic events directly.

Check this explicitly whenever delivery is healthy and decisions are absent. Confirm the incoming event name matches the trigger name, character for character.
