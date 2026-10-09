# Cloudflare MCP pagination

The optional `page` input is an integer between 1 and 10 (default: 1). The request uses GET on the fixed Cloudflare API URL and a server-validated tenant allowlist. Each page returns at most 50 provider records and a projected subset of fields. Response includes `has_more` when the Cloudflare API returns a valid `result_info.total_pages`. `partial` remains true: a page is not a verified full inventory.

The adapter does not have automatic retry or live audit persistence. Token-reference configuration, ownership evidence, staging verification, and operator logging remain rollout prerequisites. Do not assume the displayed DNS/zone list is exhaustive without traversing and validating all permitted pages. No mutation endpoints exist.
