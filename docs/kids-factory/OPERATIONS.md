# Kids Factory Operations

- Endpoints: `/api/v1/kids/overview|brands|characters|episodes|assets|render-jobs|approvals|publishing|analytics|providers|usage`.
- Writes need `operator` + `automation:write`; reads need `viewer` + `workforce:read`. Use `Idempotency-Key` on creates/renders/publishing.
- Storage: `data/kids-renders/<tenant>/<job>.mp4`; artifacts content-addressed.
- Costs: `kids_usage` ledger per episode/provider/capability; overview exposes totals.
- Recovery: failed renders can be retried (`.../retry` resets to queued); publishing resume reuses idempotency key.
- Rollback: additive tables only; drop `kids_*` tables to disable slice. No migration rewrites existing data.
