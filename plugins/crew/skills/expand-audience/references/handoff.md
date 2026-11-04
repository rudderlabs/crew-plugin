# The hand-off: from an account to a person

Expand decides about a company. Outreach decides about a person. The step between them is an event, not a tool call: Expand's one action posts the person it found to a webhook channel that points back at the same workspace, and that webhook's mapping mints the person. Any channel skill can then trigger on the event.

**What a reader is trusting.** The person Expand hands over is chosen by the model from what `research_account` returned. The trusted path around that choice is the loopback mapping (below), which turns only the profile URL field into an identity, and the human review: every found person is seen in Shadow before anyone goes Live, and every Live send waits for approval. Say this once to the user when you set the loopback up.

## 1. The loopback webhook

Create it with `webhooks_create` (needs `webhooks:write`), with the user's yes, since a webhook cannot be removed over MCP. Before that, look for one named `Crew loopback` in `webhooks_list` and compare its mapping to the one below: reuse it only when the paths match, because a loopback with another mapping mints nobody, or the wrong person, and nothing says so. Read `<PROFILE_IDENTIFIER>` from the HeyReach channel's `settings.profile_url_identifier` in `channels_list` (usually `linkedin_url`): HeyReach sends to the identifier named there, so a mapping that names another one sends to nobody.

```json
{
  "name": "Crew loopback",
  "format": "custom",
  "mapping": {
    "eventNamePath": "action",
    "messageIdPath": "decisionId",
    "identifiers": [
      { "name": "anonymous_id", "path": "decisionId" },
      { "name": "user_id", "path": "decisionOutput.payload.linkedin_url" },
      {
        "name": "<PROFILE_IDENTIFIER>",
        "path": "decisionOutput.payload.linkedin_url"
      }
    ],
    "traits": [
      { "name": "name", "path": "decisionOutput.payload.name" },
      { "name": "title", "path": "decisionOutput.payload.title" },
      { "name": "company.name", "path": "decisionOutput.payload.company_name" },
      {
        "name": "company.domain",
        "path": "decisionOutput.payload.company_domain"
      }
    ]
  }
}
```

No `externalIds`, so the mapping needs no workspace feature. Crew stores a LinkedIn profile URL under `user_id` as `https://www.linkedin.com/in/<slug>`, so the same person arriving twice is one person.

**The token.** `webhooks_create` answers the webhook's URL and bearer token once. Write them to `~/crew-lists/webhooks/<webhookId>.env` as `CREW_WEBHOOK_URL=...` and `CREW_WEBHOOK_TOKEN=...` inside one shell command with `umask 077`, and never echo either. The step 7 replay reads that file.

## 2. The loopback channel

Channels cannot be created over MCP. The user adds one in Settings → Channels: type Webhook, name `Crew loopback`, URL the webhook's URL, one header `Authorization` with value `Bearer <token>`. Give them two clipboard commands that read the file, one for the URL and one for the header value, so nothing is pasted into the chat:

```bash
sed -n 's/^CREW_WEBHOOK_URL=//p' ~/crew-lists/webhooks/<webhookId>.env | pbcopy
sed -n 's/^CREW_WEBHOOK_TOKEN=/Bearer /p' ~/crew-lists/webhooks/<webhookId>.env | pbcopy
```

Then `channels_list` for the new channel's id: that is `<LOOPBACK_CHANNEL_ID>` in the Expand body. A workspace that already has a webhook channel pointing at a loopback webhook reuses it; check the name, since the MCP never shows a channel's URL.

## 3. The lead event name

Expand's action name is the lead event name: the loopback mapping reads `action` as the event. Pick it with the user once (`<Launch> Lead Found`), and keep it to letters, digits, spaces and `_ : . / -`, which is all Crew accepts in an event name; the send script refuses anything else before it sends.

## 4. What the Outreach Agent receives

A track named `<LEAD_EVENT>` whose properties are the whole body Crew posted (`action`, `decisionId`, `userId` of the account, `eventName`, `actionRationale`, `decisionOutput.payload` with the seven fields), on a person whose traits are `name`, `title` and `company`. The Outreach Agent's lead trigger is the bare one `linkedin-outreach`'s template already has: no `when` condition. A known contact that `send-list` sent in person mode arrives on the same event with the CSV columns as properties, and the same bare trigger serves both; a `when` on `decisionOutput.payload.linkedin_url` would exclude every known contact.

## 5. Why nobody phantom is minted

`linkedin_url` is in the action's `requiredOutputFields`. A blank field is refused: when research found nobody with a profile link, the model leaves it empty, the webhook dispatcher refuses the post, and the decision is recorded on Expand as a refusal, visible on the Decisions page and countable, with the reason in `why_this_person`. Nothing reaches the loopback. In an early version without the required field, such decisions landed as people with no profile and sat in the Outreach Agent's trigger forever. The check is for emptiness, not shape: a wrong value (a company page, a word such as `n/a`) would post, and the mapping would then key the person by the decision id or by that string. That is a built or guessed URL, which the dry run and the Shadow review look for, and which the Live hand-over re-checks before Expand goes Live.

## 6. One Expand decision is one person

An Expand decision hands over one person. To reach a second person at the same account, send that account again after the dedup window (72 hours by default), or raise the limits in `guardrails`. The user can also pick from the Shadow results and send those people in person mode.

## 7. The replay: feeding Outreach from Expand's Shadow decisions

A Shadow Agent posts nothing on any channel, the loopback included. So in Shadow, Expand's findings reach Outreach only when you replay them:

1. `analytics_list` for the Expand Agent (`mode: "shadow"`, the pass's time range, `outcomes` including `delivered`), then `analytics_get` for each decision; take `decisionOutput.payload`.
2. Write `found.csv` in the list folder with the columns `linkedin_url`, `name`, `title`, `company_name`, `company_domain`, `matched_role`, `why_this_person`. Skip decisions that were refused or held.
3. Send it to the loopback webhook with the body template in this folder. `--body` makes `send_leads.py` post one event per row in the shape the webhook channel would have posted, so the same mapping mints the same person:

```bash
python3 -I <send-list>/scripts/send_leads.py --env ~/crew-lists/webhooks/<loopback webhookId>.env --file found.csv --event "<LEAD_EVENT>" --body <this folder>/loopback-body.json --pass shadow
```

The Outreach Agent then decides on each person in Shadow. At the Live cutover the same command with `--pass live` gives every found person a new event, which is what a Live Agent acts on, and costs no second research. The message id is built from the event, the pass and the person, so a repeated pass is a duplicate Crew ignores.
