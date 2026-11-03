# Find people at companies with Clay

Use the Clay MCP tool `search-contacts`. It searches public people data. It does not search the user's CRM.

- **`companyIdentifiers`**: up to 10 domains per call. If there are more companies, make more calls.
- **`dslQuery`**: starts with `select from people`. Put the ICP inside `experiences.any(is_current = true and ...)`.
- **People per company**: end the query with `limit <N> by clay_company_id`.

```text
select from people
where experiences.any(is_current = true
  and job_title contains ("data", "analytics", "growth", "marketing")
  and seniority in ("Director", "Head", "VP", "C-suite"))
limit 3 by clay_company_id
```

- `contains` matches whole words. `job_title is_similar_to ("VP Sales")` matches by meaning, but it is narrower: a test that combined it with a `seniority` filter found nobody.
- Each contact has `name`, `latest_experience_title`, `latest_experience_company`, `url` (the LinkedIn profile) and `companyIdentifier`.
- **Drop a contact whose `companyIdentifier` is not one of the domains you asked for.** Clay returns some people who have left the company.
- To get more pages, call `load-more-search-results` with the `taskId`.

Map each contact to a row: `name`, `linkedin_url` ← `url`, `title` ← `latest_experience_title`, `company` ← `latest_experience_company`, `company_domain` ← the domain you searched.
