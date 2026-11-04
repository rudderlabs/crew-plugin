# Seed: a visitor-identification feed

A tool that names the company behind a website visit (WarmAI, RB2B, or Crew's own visitor identification where the workspace has it) is already a webhook into Crew. Nothing is sent by hand; the seed event is the feed's own event.

1. `webhooks_list`: find the feed's webhook and read its mapping. The company must land under the `company.domain` trait, since that is what `research_account` resolves the company from; a mapping that leaves the domain in a property only needs the user to add the trait in the UI (mappings are edited there, not over MCP).
2. `catalog_get` on the feed's event: the exact property path of the company domain and of anything the Expand Agent should hold off on (a traffic type, a confidence level). Write the trigger `when` on those paths; the body template's `when` on `company_domain` is for the CSV seed and is replaced here.
3. Exclude the user's own domain in the same `when`.

**What differs from a CSV seed.** The feed keys each event by the visitor (an anonymous id or the visitor's profile URL), and Crew counts suppression per key, so one company is researched once per new visitor, not once per company. That is how the first production run of this Agent behaves, and it is acceptable when a company sends a handful of visitors a month. Re-keying the feed's mapping to the company merges every visitor from one company into one pseudo-person for every Agent on that webhook; it is a UI edit and the user's call, not the skill's.
