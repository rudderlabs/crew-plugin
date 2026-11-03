# Lead sourcing with treg

Three stages: detect a buying signal, qualify the company, find and check the person. **Each stage is
one shell command** that runs all its calls at once and prints one table, so the model decides three
times (which companies fit, which people to keep, the final list) instead of once per call. A treg
call takes about 4 s: the second run made them one by one and spent 2 min 20 s on calls and
3 min 20 s on the turns between them.

`<scripts>` is this skill's `scripts/` folder. `treg_batch.py` reads one JSON
line per call, `{"id": "<name>", "endpoint": "<id>", "body": {...}}`, runs six at a time, saves
`<out>/<id>.json`, skips ids already saved (a rerun pays only for failures) and prints what it charged.

## Endpoints: call these, do not search for them

They worked in the last full run (about 12 leads for $0.04). Prices below are treg's at that run; `catalog_get` all three in one turn for the
current price, then call them. `catalog_search` only when one fails or is gone: the first run lost
about 3 minutes to the endpoints under "What did not work".

| Job                 | Endpoint                          | Price                | Body                                                                            |
| ------------------- | --------------------------------- | -------------------- | ------------------------------------------------------------------------------- |
| LinkedIn jobs index | `anyapi.linkedin.search.jobs`     | $0.0005 a page of 10 | `{"query": "...", "location": "United States", "postedLimit": "month"}`         |
| Google search       | `serper.web.search`               | $0.001               | `{"q": "...", "gl": "us", "num": 10}`, plus `"tbs": "qdr:m"` for the last month |
| LinkedIn profile    | `fetchinio.linkedin.user.profile` | $0.0015              | run by `lookup_profiles.py`                                                     |

## Stage 1: hiring signal, by company

Write `signals.jsonl` with every query, then one command:

```bash
python3 -I <scripts>/treg_batch.py --out raw/signals < signals.jsonl && \
jq -rs '[.[] | (.output.data.items[]? | {c: .company, t: .title}),
  (.organic[]? | select(.link | test("greenhouse\\.io|lever\\.co|ashbyhq\\.com")) | {c: (.link | capture("//[^/]+/(?<c>[^/?#]+)").c), t: .title})]
  | group_by(.c | ascii_downcase) | sort_by(-length)[] | "\(length)\t\(.[0].c)\t\(map(.t) | unique | .[:2] | join(" · "))"' raw/signals/*.json
```

- **Jobs index:** four to eight queries in the buyer's language, e.g. `lifecycle marketing manager`,
  `CRM marketing manager`, `director lifecycle marketing`, `marketing operations manager <warehouse> <tool>`.
- **For a data or engineering buyer** the title-only index is noisy (IAM roles, staffing firms,
  enterprises; 8 pages gave about 8 usable companies). Add Serper queries over the ATS boards by
  phrase, `tbs: "qdr:m"`: `site:job-boards.greenhouse.io ("identity resolution" OR "customer 360" OR
"single customer view") (Snowflake OR BigQuery OR Databricks OR Redshift)`, and the same for
  `jobs.lever.co` and `jobs.ashbyhq.com`, with the product's own phrases. A hit names the warehouse
  and the tools, which the company enrichment then confirms.

From the table keep the companies that fit the ICP. Drop competitors and other vendors, staffing
firms, companies outside the size band, and existing customers: the companies on the product's own
logo wall, and any whose job posts name the product (in one run a company's job post listed the
product in its stack, and it was on no logo wall).

## Stage 2: the owners at each company, checked

One Serper query per company per buyer function, **one company per query** (the candidate list takes
the company from the query's last quoted name, so a query naming several companies mislabels its hits):

- Marketing: `site:linkedin.com/in ("lifecycle" OR "CRM" OR "retention") (director OR head OR VP) "<Company>"`
- Data: `site:linkedin.com/in ("head of data" OR "director of data" OR "VP of data" OR "data engineering"
OR "analytics engineering" OR "data platform") (director OR head OR VP) "<Company>"`

Then one command searches, keeps up to three hits per company whose title matches both the seniority
and the function, and checks every one of them (about $0.0015 each; 16 for eleven companies in a replay of the second run, 9 of them current). It
skips a hit whose Google subtitle names another company: in the second run all 12 such hits had
moved on, and no current one was lost.

```bash
python3 -I <scripts>/treg_batch.py --out raw/owners < owners.jsonl && \
jq -rs '["name","linkedin_url","company"], (map((.searchParameters.q | [scan("\"([^\"]+)\"")[0]] | last) as $co
  | [.organic[]? | select(.link | test("//(www\\.)?linkedin\\.com/in/"))
     | select("\(.title) \(.subtitle // "")" | test("head|director|vp|vice president|chief|svp"; "i") and test("<function regex>"; "i"))
     | select((.subtitle // "") as $s | $s == "" or ($s | ascii_downcase | contains($co | ascii_downcase | split(" ")[0])))][:3]
  | map({n: (.title | split(" - ")[0]), u: (.link | sub("[?#].*"; "")), c: $co})) | add | unique_by(.u)[] | [.n, .u, .c]) | @csv' \
  raw/owners/*.json > candidates.csv && \
python3 -I <scripts>/lookup_profiles.py --leads candidates.csv --out checked.csv --cache raw/profiles
```

`<function regex>` is the buyer's words, e.g. `data|analytics` or `lifecycle|crm|retention|growth`.
`(www\.)?` keeps US-locale profiles only; drop it when the ICP is not US-only. The table shows each
candidate's current title, company, country and status from their profile, which is what to pick from:
Google snippets go stale (in the first run a "Head of CRM" had left a month earlier; in the second,
2 of 14 had moved company).

## Stage 3: the list

Max two people per company, `CURRENT` only. Prefer the hiring manager of the open role (the director
above a "Manager" opening, the CMO or VP above a "Director" opening). Write `leads.csv` with the
checked title, then rerun `lookup_profiles.py` on it for `member_ids.csv` (every profile is cached,
so it costs nothing).

## Demo mode: about a minute, accuracy a little off

When the user says it is a demo or wants it fast, skip the hiring signal and the picking:

1. Name 6–8 companies that fit the ICP from what you know (US, the right segment and size; no
   vendors, no existing customers) and write Stage 2's owner query for each into `owners.jsonl`.
2. Run Stage 2's command with its last line changed to
   `python3 -I <scripts>/lookup_profiles.py --leads candidates.csv --out member_ids.csv --cache raw/profiles --leads-out leads.csv --limit 10 --workers 12 --prefer '<buyer title words>'`.
   `--prefer` (a regex such as `platform|engineering`) picks the buyer's titles first; without it the
   third run's pick favoured data-science titles over the platform owners it wanted.
   It searches, checks and writes `leads.csv` (`CURRENT` only, two per company) and `member_ids.csv`
   in one go. Show the table and carry on; Stage 3 and the step-3 rerun are not needed.

About $0.03 and under a minute of calls (17 checks at six at a time took 23 s). What it
gives up: no hiring signal, so no `talking_point`, and the companies come from the model's knowledge,
so a few may fit the ICP less well.

## What did not work

- **LinkedIn post search** (`anyapi.linkedin.search.posts`, about $0.008 a page): pain-keyword
  queries returned vendors, consultants, students and agencies. Buyers rarely post the pain.
- **LinkedIn profile search by title and company** (`harvestapi.linkedin.profile.search`, $0.004):
  out-of-network profiles come back as hidden "LinkedIn Member" rows with no URL (9 of 10).
- **Apollo people search** (free): no LinkedIn URL and an obfuscated last name.
- **Email finding**: not needed. HeyReach only needs the profile URL.

## Mechanics

- Full responses stay in `raw/`; print only the table (a full profile is about 25 KB).
- `talking_point` only when the signal is about the person's own team, phrased neutrally
  ("<Company> has an open <role> role, posted on LinkedIn in <month>"). Never the reason we picked them.
- Outreach to EU and UK people needs a lawful basis; say so once before handing over the list.
