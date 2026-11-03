# A list that keeps sending: RudderStack Reverse ETL to Crew

Use this instead of `send_leads.py` when the list is more than a few hundred people, or when the people who join it later should reach the Agent too. RudderStack reads the list from the warehouse on a schedule and posts each new or changed row to a Crew webhook as an event. The Agent decides on each one as it arrives.

```text
warehouse query (a Reverse ETL model) ─▶ RudderStack Webhook destination ─▶ Crew webhook ─▶ the Agent's trigger
```

**What is checked, and what is not.** The Crew half has been run for real: events shaped the way RudderStack's Webhook destination delivers a Reverse ETL row were sent to a Crew webhook. The rows were accepted, an identify wrote the profile email (the connection in step 3 sends only tracks, so step 4 checks the other way the email reaches a Customer.io Agent), the track triggered the Agent, and a decision drafted an email from the row's columns. The RudderStack half comes from RudderStack's open-source code: its Webhook destination takes warehouse (Reverse ETL) sources and posts the whole event as the request body (`rudder-integrations-config`, `rudder-transformer`). Nobody has run a full sync from a warehouse yet, so the first sync in step 4 is the test.

A Lookout audience cannot be the source: RudderStack connects an audience source only to audience and list destinations, and a Webhook destination is neither. Use the audience's filter as a model instead.

## 1. Crew: the Agent and a webhook (Claude)

Pick the Agent as in step 4 of the skill. Create a webhook for this list as in step 5, named for the list, with `format: "rudderstack"`. Do not reuse a webhook another source sends to, and never point this at an existing RudderStack destination that feeds Crew: such a destination often has a transformation that reshapes every event.

## 2. The model (Claude)

Write the SQL RudderStack will run: the recipe's fetch query ([recipes/lookout-audience.md](recipes/lookout-audience.md), step 3) without `ORDER BY` and `LIMIT`. It must return the email and the user id as text, the name, and the columns the Agent needs. Show it to the user, with the count from the recipe.

## 3. RudderStack: the destination and the source (the user)

These steps hold a credential, so the user does them in RudderStack. Give them the values; never print the token. Tell them it is in `~/crew-lists/webhooks/<webhookId>.env`.

1. **Destination.** Add a Webhook destination. URL: `CREW_WEBHOOK_URL` from that file. Method: POST. Header: `Authorization` with the value `Bearer <CREW_WEBHOOK_TOKEN>`.
2. **Source.** Add a Reverse ETL source on the warehouse, as a **Model**, with the SQL from step 2.
3. **Connect the source to the destination.**
   - Sync mode **Upsert**: it sends rows that are new or changed since the last sync. Mirror cannot send track events.
   - Event type **Track**, with the Agent's trigger event as a fixed event name.
   - User identifier: `user_id` set to the id column; the email column if there is no id.
   - Map the email, the name and every column the Agent needs.
   - RudderStack does not let you change the sync mode, the event type or the user identifier after you save. To change one, delete the connection and connect again.

## 4. The first sync: one row (Claude checks, the user syncs)

Change the model to return one row (add `LIMIT 1`), and have the user press **Sync now**. Then check:

- RudderStack's Live Events for the destination show the event delivered.
- `analytics_list` for the Agent shows a decision for that person.
- In Crew, Events → the trigger event: `properties.email` is marked as an identifier. If it is not, the user marks it there. A Customer.io Agent sends to that address when the person has no profile email, and Crew's own marking can come after the first events: in that test run, the first event on a new webhook arrived with no email identifier, so a Customer.io send for it would have failed with no recipient.

Then put the full query back. RudderStack's first sync sends every row, whatever the mode.

## 5. Schedule

**Manual** for a list sent once, **Basic** (an interval) or **CRON** (in UTC) for a list that keeps growing. Start the Agent in Shadow; only a human takes it Live.

## Rows Crew refuses

Crew answers these with a 400, and RudderStack's Webhook destination does not retry a 4xx, so the row is lost (each seen in that test run):

- An event name with any character other than letters, digits, spaces and `_ : . / -`, for example parentheses. Use a fixed name.
- A user id that is a number. Cast it to text in the model.
- A timestamp with no time zone mapped onto the event's own timestamp. Do not map a timestamp there; send it as a property, formatted as a date.

## Every change is a new decision

Upsert re-sends a row whenever any mapped column changes, and the Agent decides on that person again. Map only the columns that should prompt a new decision, leave out values that change on every sync, and keep the Agent's deduplication limit on.
