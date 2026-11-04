---
type: regex
target: { source: file, path: loopback-mapping.json }
pattern: '"identifiers"\s*:\s*\[[^\]]*"user_id"[^{}\]]*"decisionOutput\.payload\.linkedin_url"|"identifiers"\s*:\s*\[[^\]]*"decisionOutput\.payload\.linkedin_url"[^{}\]]*"user_id"'
---
