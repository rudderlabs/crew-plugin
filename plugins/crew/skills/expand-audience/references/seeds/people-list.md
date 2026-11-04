# Seed: a list of people whose companies to expand

A LinkedIn connections export (`First Name`, `Last Name`, `URL`, `Email Address`, `Company`, `Position`, `Connected On`) or a CRM export of contacts. It holds two seeds at once, and the user picks one or both:

- **The people themselves are known contacts.** `name` is first and last name joined, `linkedin_url` is `URL`, `title` is `Position`, `company` is `Company`, and `is_connection` is `true` for a connections export. They go to `people.csv` and to the Outreach Agent's lead event in person mode, as `accounts-csv.md` step 4 says.
- **Their companies are accounts to expand.** One row per distinct `Company`, with the domain resolved as in `accounts-csv.md` step 1. A people list usually carries company names and no domains, so that step is where the time goes; show the user the domains before sending. They go to `accounts.csv`.

Drop the user's own company and companies with no resolvable domain. Keep `Connected On` out of the event: a date the person never gave us reads as tracking when it reaches a message.
