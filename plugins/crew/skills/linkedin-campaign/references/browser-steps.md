# Browser steps (only when the user opts in)

Creating a webhook with its mapping is `webhooks_create` over the Crew MCP (SKILL.md step 6). Use
these screens only when that tool is missing (the token lacks `webhooks:write`) or to change an
existing webhook's mapping, which the MCP leaves out on purpose: it changes
how every later event on that webhook resolves identity. Driving the UI does not change who decides.
Use the browser on the user's Crew UI (their Crew URL); the user signs in first.

## Create the custom webhook (fallback)

1. Settings → Integrations → **Webhooks** card → **New webhook**. Name `<Launch> leads (custom)`,
   Payload format **Custom**.
2. **Stop before Create webhook.** The user clicks it and puts the URL and token into
   `<launch>/crew-webhooks.env` as `CREW_CUSTOM_WEBHOOK_URL` and `CREW_CUSTOM_WEBHOOK_TOKEN` (SKILL.md
   step 6). Never read the token off the screen: a screenshot puts it in the transcript.
3. Check with `webhooks_list` and compare the id inside the shell, without printing it.

## Map it (a webhook created in the UI, or changing an existing mapping)

1. Settings → Integrations → the new source → expand **Field mapping**. No sample event is needed:
   the panel takes paths typed by hand.
2. Fill: Action path `event`; Message id path `messageId`; **+ Add external id** → namespace
   **LinkedIn member id**, path `memberId`; **+ Add identifier** → name `user_id`, path `userId`.
3. Screenshot the filled form for the user and **ask before clicking Confirm mapping**. Saving makes
   it active for every later event on that source.
4. Check with `webhooks_list`: `mappingStatus: "active"` and the four paths.

## Never

Going Live, connecting HeyReach (an API key), and any HeyReach campaign or send. Those stay the
user's, whatever browser access exists.
