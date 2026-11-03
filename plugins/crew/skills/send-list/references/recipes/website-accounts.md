# Recipe: top accounts that visited the website

Finds companies whose people visit the website often, removes companies the user does not want (customers, for example), and finds people who fit the ICP at the companies that are left.

Ask for these, or use the defaults:

| Input                  | Default                                             |
| ---------------------- | --------------------------------------------------- |
| Website host           | the company's `www.` host                           |
| Product app's source   | none                                                |
| Window                 | 30 days                                             |
| What "top" means       | visits on 3 or more distinct days                   |
| Which segments to keep | trial accounts and accounts that never used the app |
| ICP                    | ask the user; there is no default                   |
| People per account     | 3                                                   |

**Stages and files** (for the funnel): `accounts.csv` after step 2 (the window and the day threshold), `accounts-kept.csv` after step 3 (the segments and customer source), `people.csv` after step 4 (the ICP and people per account). The evidence for each person, one entry per source in `evidence.json`:

- `Warehouse`. why: `16 people from acme.com visited www.example.com on 17 days in the last 30 days; segment trial`. facts: `visit_days`, `visit_people`, `segment`. basis: `<schema>.pages, host <site host>, email domain acme.com, last 30 days; segment from <app schema>.tracks trial events`.
- `Clay`. why: `Current role: Head of Data at Acme`. facts: `title`, `company`. basis: the `search-contacts` query, for example `job_title contains (data, analytics), seniority Director+, acme.com`.

## 1. Find the events

The events are in the user's own warehouse, where a RudderStack warehouse destination writes each source to its own schema: the website's page views to `<site schema>.pages`, and the app's events to `<app schema>.tracks`. Use the warehouse MCP the user has connected (Snowflake, BigQuery, a Lookout warehouse, ...), and ask which schemas belong to the website and the app if more than one could be right.

Do not assume column or event names. Read a few rows of each table first. The fields this recipe needs, under the names RudderStack's warehouse destinations usually give them:

- `context_page_url`: the page. Its host tells the website from the app.
- `context_traits_email`: the visitor's email, when the visitor is identified. If it is empty, the `users` table in the same schema has `email` by `id` (the `user_id`).
- `event` (in `tracks`): the event name, for the app's trial or plan events.

Only identified visitors carry an email, so only they can be matched to a company. Tell the user how many visitors were identified out of the total. Anonymous visitors need IP-to-company matching, and that is not in the warehouse.

## 2. Rank the accounts

The query below is Snowflake; for another warehouse, swap the URL, date and string functions. It comes from a version that ran on a different event store, so check the counts look sane before you show them.

```sql
WITH raw AS (
  SELECT 'site' AS src,
         coalesce(p.context_traits_email, u.email) AS email,
         lower(parse_url(p.context_page_url):host::string) AS host,
         NULL AS ev,
         coalesce(p.user_id, p.anonymous_id) AS who,
         to_date(p.received_at) AS d
  FROM <site schema>.pages p
  LEFT JOIN <site schema>.users u ON u.id = p.user_id
  WHERE p.received_at > dateadd(day, -90, current_timestamp())
  UNION ALL
  SELECT 'app',
         coalesce(t.context_traits_email, u.email),
         lower(parse_url(t.context_page_url):host::string),
         t.event,
         coalesce(t.user_id, t.anonymous_id),
         to_date(t.received_at)
  FROM <app schema>.tracks t
  LEFT JOIN <app schema>.users u ON u.id = t.user_id
  WHERE t.received_at > dateadd(day, -90, current_timestamp())),
e AS (
  SELECT src, lower(split_part(email, '@', 2)) AS dom, host, ev, who, d FROM raw WHERE email LIKE '%@%'),
site AS (
  SELECT dom, count(DISTINCT d) AS days, count(DISTINCT who) AS people, count(*) AS events
  FROM e WHERE src = 'site' AND host = '<site host>' AND d > dateadd(day, -<window>, current_date())
  GROUP BY dom HAVING count(DISTINCT d) >= <min days>),
app AS (
  SELECT dom, max(iff(ev IN ('<trial event>', '<another trial event>'), 1, 0)) AS trial
  FROM e WHERE src = 'app' GROUP BY dom)
SELECT site.dom, days, people, events,
       CASE WHEN app.dom IS NULL THEN 'never used app' WHEN app.trial = 1 THEN 'trial' ELSE 'app user' END AS segment
FROM site LEFT JOIN app ON site.dom = app.dom
WHERE site.dom NOT IN ('gmail.com', 'googlemail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com',
                       'live.com', 'aol.com', 'proton.me', 'protonmail.com', 'qq.com', '163.com', '<own domain>')
ORDER BY people DESC, days DESC
LIMIT 500
```

Fill in the product's trial or plan events from step 1 (for example `trialStarted` and `trialCompleted`). App activity is every event in the app's source, server-side ones included; those carry no page URL, which is why the app half is matched by its source, not by a host. The email comes from `context_traits_email` or, failing that, the schema's `users` table; leave out whichever of the two a schema doesn't have. The `LIMIT` is there because some warehouse tools refuse a query without one, and it cuts the list: if exactly 500 rows come back, raise it before step 3 drops customers, or prospects past the cut never reach the list. Take step 3's segment counts from the same query without its `ORDER BY` and `LIMIT`, wrapped as `SELECT segment, count(*) AS accounts FROM (…) GROUP BY segment LIMIT 10`, never from the capped rows. If there is no app, leave out the `tracks` half, `app` and `segment`. The free-mail list is not complete: also drop any other free-mail domain you recognise (`rocketmail.com`, for example).

## 3. The user picks the accounts: stop here

Show the number of accounts in each segment first. When visitors are identified mostly by logging in to the app, `never used app` is small: on one B2B product's site it was a handful of accounts against hundreds of app users, because almost every identified visitor had been identified by logging in. Check how visitors get identified before reading that segment as prospect traffic.

The segment is only a hint. One person who starts a trial puts the whole company in `trial`, even when the company already pays. Customer status comes from the CRM: if a CRM MCP is connected (Salesforce, HubSpot), or the user has a file of customer domains, drop those domains, and tell the user which source you used. If there is neither, say that customers can still be in the list.

Show the top accounts of the segments the user keeps (domain, days, people, segment), and let the user remove some.

## 4. Find the people

Follow [../clay-people.md](../clay-people.md) with the user's ICP, 10 domains per call. Put the visit facts in the `Warehouse` entry of `evidence.json` only. Do not put them in `why_now`: it goes to the Agent, and in a test run the Agent turned `16 people visited <our site>` into "growing interest from <company>" in the message. Set `why_now` to the person's fit, for example `Leads data and analytics at Acme`.

Write `list.csv`, then go back to step 2 of the skill.
