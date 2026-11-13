# HeyReach campaigns, created by the skill

**Crew sequences; HeyReach executes one touch.** So derive the campaigns from the Agent's moves,
one campaign per move that needs one, and decide everything else per launch. Do not copy a fixed
set, and do not build multi-step sequences.

## The rule

- **One outreach step per campaign, then END.** A step that sends text holds exactly one Crew
  variable; a warm-up step holds none. The only node allowed in front of it is
  `CHECK_IS_CONNECTION` (a `MESSAGE` must sit on its connected side).
- **Why:** with a second outreach step HeyReach decides when it fires, its text is written at enroll
  time before Crew knows what happened, HeyReach cannot branch on anything Crew knows, and a person
  goes through a campaign once. Each of these takes the next move away from the Agent.
- **Replies need no campaign.** The Reply move is a direct message (`heyreachDirectMessage: true`)
  into the existing conversation, and so is every message after the first.
- **New campaigns per launch.** A person goes through a campaign once and an old one holds other
  leads. A Shadow-only rehearsal may reuse existing ones; say which.

## Choose the moves

Start from the Agent's moves (linkedin-outreach: Connect, Message, Reply), check what the
sender can do with `get_all_linked_in_accounts` (`authIsValid`, cooldowns, `isValidNavigator`), and
propose the moves that suit this buyer. Each move is one more thing the Agent can choose; it decides
when.

| Move                   | Campaign shape                             | Variable                                             | Offer it                                                                                                                              |
| ---------------------- | ------------------------------------------ | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Connect                | `CONNECTION_REQUEST` → END (both branches) | `crew_connection_note` (≤200 chars on free accounts) | always                                                                                                                                |
| Message                | `CHECK_IS_CONNECTION` → `MESSAGE` → END    | `crew_message`                                       | always                                                                                                                                |
| View profile           | `VIEW_PROFILE` → END                       | none                                                 | for cold leads: a light first touch; they see a view, nothing to read                                                                 |
| Follow                 | `FOLLOW` → END                             | none                                                 | for leads who post: a light touch that keeps their posts in the sender's feed                                                         |
| Like their latest post | `LIKE_POST` → END                          | none                                                 | only with the caveat: HeyReach likes their most recent post and nobody reads it first, so it can like a post about a layoff or a loss |
| InMail                 | `INMAIL` → END                             | `crew_inmail`                                        | only if the sender has Sales Navigator or Premium (`isValidNavigator`) and the ICP is hard to reach by connecting                     |

HeyReach has no comment step and no reaction other than a like. **The warm-up moves are new in
Crew:** it accepts a campaign with no variable, but no run has sent one yet. Dry-run and Shadow them
like the rest, and suggest "needs approval" on them for the first Live batch.

Per campaign, decide and show the user: the name (`<Launch> · <Move>`, ≤50 chars), the senders,
the schedule (the sender's working hours in their own time zone; HeyReach's default is Mon–Fri
09:00–17:00 UTC, and a lead enrolled outside the window waits), the connection-request withdraw
days, a neutral fallback text for a step with a variable (sent when the variable is empty), and the
exclusion flags: keep the blacklist ones on, and keep `excludeContactedFromOtherCampaigns` and
`excludeContactedFromSenderInOtherCampaign` **off**. On, they exclude a lead who accepted the Connect
campaign from the Message campaign.

## Add a move to the Agent

A move beyond the template's three needs its own Act, Option, action policy and available action
in the Agent body, written like the others. The Option says what the move is and what it can reach,
never when to use it. For View profile:

```json
{
  "acts": [{ "id": "view", "name": "View their LinkedIn profile" }],
  "options": [
    {
      "id": "view",
      "name": "View their LinkedIn profile",
      "actId": "view",
      "whenToPrefer": "Views their LinkedIn profile from the sender's account; they may see the view, and nothing is sent for them to read. It reaches only someone we have not contacted yet, and each person once."
    }
  ],
  "actionPolicies": [
    {
      "id": "view_profile_on_linkedin",
      "actId": "view",
      "action": "View their LinkedIn profile",
      "channelId": "<HEYREACH_CHANNEL_ID>"
    }
  ],
  "availableActions": [
    {
      "id": "view_profile_on_linkedin",
      "type": "View their LinkedIn profile",
      "channel": "heyreach",
      "enabled": true,
      "payloadTemplate": {
        "prompt": "This move sends no text. Write nothing.",
        "requiredInputs": [],
        "optionalInputs": [],
        "outputFields": []
      },
      "heyreachCampaign": { "id": "<VIEW_CAMPAIGN_ID>", "name": "<Launch> · View profile", "variables": [] }
    }
  ]
}
```

On a managed channel the campaign already exists: set `heyreachCampaign` to the `bind.fields.heyreachCampaign` of the
matching item from `channels_resources` (View profile, Follow or Like a recent post) instead of writing it.

These merge into `decisionLogic.acts`, `decisionLogic.options`, `decisionLogic.actionPolicies` and
`availableActions`. Follow and Like follow the same pattern. Add the move to the "Where things stand"
signal too ("have we already viewed, followed or liked?"), since HeyReach reports nothing back about
them.

## Reads first (no approval needed)

- `get_all_linked_in_accounts`: sender ids and what each can do.
- `get_all_campaigns` with `keyword: "<Launch>"`: reuse a campaign this skill already made for this
  launch rather than making a second.
- `get_campaigns_for_lead` for each lead: drop anyone still active in another campaign, or they get
  two conversations from the team at once.
- `get_campaign_sequence` on a working Crew campaign: its JSON is a valid sequence to adapt.

## Writes, after the user says yes

Every write acts on the team's real LinkedIn sender. Use the **HeyReach MCP** (a claude.ai connector
or `claude mcp add`). No MCP: the same calls exist in HeyReach's API at
`https://api.heyreach.io/api/public/` (`list/CreateEmptyList`, `campaign/Create`,
`campaign/StartCampaign`), with header `X-API-KEY` read from `<launch>/heyreach.env` inside the
command that calls it, and passed so it stays out of the process list:
`(set -a && . <launch>/heyreach.env && set +a && curl -sS -H @<(printf 'X-API-KEY: %s\n' "$HEYREACH_API_KEY") …)`.

1. `create_empty_list` (`USER_LIST`) per campaign.
2. `create_campaign` with the list, senders, schedule and `sequenceJson`. Delays: 0 on the first
   node; at least 3 hours on every node that follows an outreach step (`CONNECTION_REQUEST`,
   `MESSAGE`, `INMAIL`, `VIEW_PROFILE`, `FOLLOW`, `LIKE_POST`), END included, or the API refuses. Two
   ENDs may stay at 0: a `MESSAGE`'s reply-exit (its `conditionalNode`) and anything after a `CHECK_`
   node. Known-good shapes:

   ```json
   {
     "nodeType": "CONNECTION_REQUEST",
     "actionDelay": 0,
     "actionDelayUnit": "HOUR",
     "payload": {
       "messages": ["{crew_connection_note}"],
       "fallbackMessage": "Hi {FIRST_NAME}, good to connect.",
       "toBeWithdrawnAfterDays": 14
     },
     "conditionalNode": { "nodeType": "END", "actionDelay": 3, "actionDelayUnit": "HOUR" },
     "unconditionalNode": { "nodeType": "END", "actionDelay": 3, "actionDelayUnit": "HOUR" }
   }
   ```

   ```json
   {
     "nodeType": "CHECK_IS_CONNECTION",
     "actionDelay": 0,
     "actionDelayUnit": "HOUR",
     "conditionalNode": {
       "nodeType": "MESSAGE",
       "actionDelay": 0,
       "actionDelayUnit": "HOUR",
       "payload": { "messages": ["{crew_message}"], "fallbackMessage": "Hi {FIRST_NAME}, thanks for connecting." },
       "conditionalNode": { "nodeType": "END", "actionDelay": 0, "actionDelayUnit": "HOUR" },
       "unconditionalNode": { "nodeType": "END", "actionDelay": 3, "actionDelayUnit": "HOUR" }
     },
     "unconditionalNode": { "nodeType": "END", "actionDelay": 0, "actionDelayUnit": "HOUR" }
   }
   ```

   A warm-up step takes only an `unconditionalNode`, here `VIEW_PROFILE` and the same with `FOLLOW` or
   `LIKE_POST` (not yet created in a run; the shape follows HeyReach's own rules):

   ```json
   {
     "nodeType": "VIEW_PROFILE",
     "actionDelay": 0,
     "actionDelayUnit": "HOUR",
     "unconditionalNode": { "nodeType": "END", "actionDelay": 3, "actionDelayUnit": "HOUR" }
   }
   ```

3. `start_campaign` on each. Crew refuses to enroll into a paused or draft campaign. An empty
   started campaign sends nothing and turns FINISHED within minutes; Crew's enroll resumes it.

Then bind each campaign to its action in the Agent body (`heyreachCampaign`: id, name, the variable
and where it sits, e.g. `step 1, connection note`, `step 2, message`, or no variables for a warm-up
move). Crew reads each campaign from HeyReach when the Agent is created and when a body is
published, and stamps HeyReach's own name, variables and places over what you wrote; a draft save
does not re-read. Switching the Agent onto Shadow or Live checks the campaign again and discards the
result. `agent_get` only returns what is stored, so check it after `draft_publish` or the switch to
Shadow: a variable missing there is missing from the campaign. A refused create, publish or switch
(`HEYREACH_CAMPAIGN_UNUSABLE`, `HEYREACH_CHANNEL_MISMATCH`, `HEYREACH_CAMPAIGN_WITHOUT_CHANNEL`) means
the campaign is unusable: fix it in HeyReach, not in the body. When HeyReach cannot be reached the
written copy is kept and the write goes through.

## Limits that shape the choice

- About 25 connection requests a day per sender; HeyReach freezes a sender near ~100 a week.
- Free LinkedIn accounts get 200-character notes and only a few notes a month; past that, HeyReach
  sends the request without a note.
- Views, follows and likes are LinkedIn activity on the sender's account too, which HeyReach paces.
- One shared API limit of 300 requests a minute per key.
