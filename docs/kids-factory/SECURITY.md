# Kids Factory Security

Threats: prompt injection, untrusted provider output, upload abuse, SSRF, traversal, cross-tenant access, token theft, worker escalation, unauthorized publishing, duplicate charges, artifact tampering, secret disclosure, supply chain.

Controls in slice:

- Tenant check on every read/write; cross-tenant returns 404, never leaks existence.
- Server-side secrets only; browser receives no provider keys.
- Upload guard: allowlisted content-type/extension, size cap, no path separators, no URL filenames.
- Render paths confined under data dir; `..` rejected; subprocess uses arg list, `shell=False`.
- Publishing requires approved approval for the same episode.
- Audit rows for brand/character/episode/script/scene/asset/timeline/render/approval/moderation/publishing.
- Secret-like strings rejected by validation; destructive patterns not executed.
