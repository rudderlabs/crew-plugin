---
type: regex
target: { source: file, path: expand-agent.json }
pattern: '"operator"\s*:\s*"(!=|not_equals)"[^{}]*"value"\s*:\s*"example\.com"|"value"\s*:\s*"example\.com"[^{}]*"operator"\s*:\s*"(!=|not_equals)"'
---
