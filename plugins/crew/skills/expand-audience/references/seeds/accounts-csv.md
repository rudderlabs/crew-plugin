# Seed: a CSV of accounts

One row per company the user wants a person at, optionally with the person they already know there.

| Column                                   |                                                                                                                                                                                                                           |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `company_domain`                         | Required. A bare domain (`acme.com`). A scheme, `www.` or a path is stripped by the send script; a free-mail domain is refused.                                                                                           |
| `company`                                | The company's name.                                                                                                                                                                                                       |
| `segment`, any other column              | Becomes an event property the Expand Agent reads and the Outreach Agent inherits in `why_this_person`'s company. Only what is fine to say.                                                                                |
| `name`, `linkedin_url`, `email`, `title` | A person the user already knows at that company. A row with one is a person, not an account; give it an `id` equal to the profile URL, as `people-list.md` says, so the person is one person whichever path reaches them. |

## Steps

1. **Fill in domains.** A list from a CRM or a spreadsheet often has company names and no domains. One web search per company; show the table (company, domain found, the page it came from) and let the user correct it before anything is sent. A wrong domain researches the wrong company.
2. **Drop what research cannot use:** free-mail domains and the user's own domains. The send script refuses free mail too, but the user should see the drop.
3. **Split.** Rows with a `linkedin_url` or `email` go to `people.csv`; the rest to `accounts.csv`. Save both in `~/crew-lists/<slug>/` with the folder and file modes `send-list` uses, and show the funnel line (`74 rows → 70 with a domain → 61 accounts + 9 known people`).
4. **Send each to its own event.** `accounts.csv` goes to `<SEED_EVENT>` with `--entity account`; `people.csv` goes to `<LEAD_EVENT>` in `send-list`'s person mode, straight to the Outreach Agent, never through Expand. The commands are in SKILL.md.

A LinkedIn connections export is a people list: see `people-list.md`.
