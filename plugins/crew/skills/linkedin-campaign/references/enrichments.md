# Research enrichments for LinkedIn leads

Two `research` definitions per file, ready for `enrichment_create`. Pick the file whose buyer is
closest, then rewrite the company brief's items 2–5 and the outputs for what the product touches.
Replace `<Launch>`, `<MONTH YEAR>` (six months back), and the Tavily entry: take its `connectionId`
and exact tool name from `mcp_listTools` (only tools with `enrichmentReadAllowed`), or drop it and
keep the built-in `web_search` and `web_fetch` (they exist only where the workspace has web search
on; with it off, research gets no search tool and comes back empty).

| File                                           | Buyer                                                            | Company outputs                                                                                          |
| ---------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| [enrichments.json](enrichments.json)           | lifecycle / CRM / marketing (an audience-building product's run) | `business`, `warehouse`, `marketing_stack`, `audience_workflow`, `company_talking_point`, `evidence_url` |
| [enrichments-data.json](enrichments-data.json) | data / analytics engineering (an identity product's run)         | `business`, `warehouse`, `data_stack`, `identity_context`, `company_talking_point`, `evidence_url`       |

Both files carry the same person definition: `focus`, `recent_public_item`, `evidence_url`.

A fact the Fit rule depends on (for example "already uses <product>") needs its own `boolean` or
`text` output: `text_list` outputs are often refused (below), and a refused field never reaches the
decision.

## Before saving

`enrichment_preview` takes the definition, not an id, so test before you create. Pass an ad-hoc
subject with the member id, or research refuses with `missing_input` ("research needs an email,
phone, external id, or a LinkedIn profile URL as the user ID"). The `linkedin:<slug>` user id these
leads carry is not a LinkedIn profile URL, so it does not count:

```json
{
  "userId": "linkedin:<slug>",
  "externalIds": { "linkedin.member_id": "<memberId>" },
  "traits": { "name": "<name>", "firstName": "<first>", "title": "<title>", "company": "<company>" }
}
```

Show the user two previews of each. An empty person result is correct when nothing public exists.

## What to expect (first real run, 11 leads)

- **Company research is good when the company posts jobs.** A company's own lifecycle or MarTech job
  post named Braze or Iterable with near-certain evidence. Without one, stack fields stay empty
  (the evidence check rejects unsupported claims, which is right).
- **Person research is mostly empty.** Built-in web search cannot read LinkedIn posts; it found
  people with press or podcast coverage (2 of 5). A LinkedIn-posts tool connected to Crew as an
  outbound MCP (with `enrichmentReadAllowed`) would fill it.
- **Company research runs per person**, not per company: two people at one company got different
  facts and paid twice.
- **The date window leaks**: the model still returned an item from the year before and a routine blog
  page as the "recent item". The Agent's copy rules filter those out; keep them.
- **Dates can be invented** (an interview dated a month in the future). Never let the Agent quote a date.
- **Empty and partial results are cached for 15 minutes**, so a Shadow pass or a Dry Run
  re-researches people with no result.
- **A Dry Run enriches a person who has no current result**, exactly as Live does, and keeps it, so
  the next Dry Run or Shadow pass reuses it. It needs a real person: a made-up `userId` has nothing
  to enrich.

## What to expect (second real run, an identity product, 10 data leaders)

- **The company's own data-role job post is the best source**: one company's Lever post gave its
  warehouse, eight tools and "debug identity resolution" in one fetch. A warehouse came back for 3 of
  the 5 companies refreshed, and for one more in the Shadow pass; none for the last two.
- **`text_list` outputs are refused by the evidence check most of the time** (`data_stack` refused in 4
  of 7 runs, even when the excerpt named every tool), and one `warehouse` was refused from a source
  that passed twice. The check is not deterministic: preview twice before judging a brief.
- **A brief rule alone does not stop non-answers**: with "leave it empty" only in the brief, 2 of 2
  previews wrote "I found no public source…" into `identity_context`. Putting the rule in the output's
  description stopped it.
- **The recent item drifts to brand news** (a celebrity spokesperson stunt) unless the brief excludes
  it and prefers the company's own open data role.
- **Person research found something for 3 of 5**, all two or more years old or wrongly dated (a post
  announcing they had joined, dated more than a year before they started).
