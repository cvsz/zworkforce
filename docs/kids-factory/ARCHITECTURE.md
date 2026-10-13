# Kids Factory Architecture

Vertical slice on the zWorkforce control plane. No second orchestration framework.

- Domain: `zworkforce/kids_factory.py` (validation, safety, storyboard, render, mock YouTube).
- Persistence: `zworkforce/db_schema_kids.py` + `zworkforce/db_kids.py` (tenant-scoped, SQLite/PostgreSQL portable).
- Transport: `zworkforce/kids_api.py` under `/api/v1/kids/*`, RBAC viewer/operator, audit on every mutation.
- MCP: `zworkforce/kids_mcp.py` (`kids.*`, mutations deny-by-default, require `automation:write`).
- UI: Kids Studio panel in `zworkforce/static` reads live backend state only.
- Reuse: artifacts (SHA-256), audit chain, budgets/usage, dashboard events, policy engine, FFmpeg local render.

Brand snapshots are immutable per version. Character versions are immutable. Publishing requires an approved approval row.
