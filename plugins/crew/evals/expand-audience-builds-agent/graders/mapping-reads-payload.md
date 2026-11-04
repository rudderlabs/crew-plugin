---
type: regex
target: { source: file, path: loopback-mapping.json }
pattern: '"user_id"[^{}]*"decisionOutput\.payload\.linkedin_url"|"decisionOutput\.payload\.linkedin_url"[^{}]*"user_id"'
---
