# Data Ownership

## Persistent data stores

### 1. Agent Provider durable JSON store

- **Owner:** `services/agent-provider`
- **Location:** Docker volume `agent-provider-data` (path `/data` in container), file `state.json`
- **Schema:** JSON document with namespaces `jobs`, `idempotency`, `queue`, `audit`, `workspaces`, `restoreNamespaces`
- **Migrations:** None (JSON file, versioned in-place)
- **Retention:** Indefinite (operator-managed cleanup via `/workspaces/cleanup`)
- **Backup:** `GET /backup/export` returns full snapshot; `POST /backup/restore` imports snapshot with namespace isolation
- **Restore:** Namespace-isolated restore with SHA-256 digest verification
- **PII classification:** May contain tenant IDs, subject IDs, objectives, tool grants — treat as PII
- **Tenant ownership:** Implicit via `job.tenant_id` and `workspace.id`; no hard tenant isolation at storage layer
- **Deletion semantics:** No automatic deletion; manual cleanup required
- **Encryption:** None at rest (plain JSON on disk)
- **Indexing:** In-memory Maps; no external index
- **Observability:** Prometheus metrics (`z_platform_agent_*`), audit events emitted to `/events`

### 2. Redis (ai-gateway, phase6-api, zc)

- **Owner:** `services/ai-gateway` (provider key pools), `services/phase6-api` (alerts, sessions, webhooks), `services/zc` (cache)
- **Location:** Docker service `redis` (Compose), URL `redis://redis:6379`
- **Schema:** Key-value with TTLs
  - ai-gateway: `provider:<name>:active_keys`, `provider:<name>:cooldown_keys:<key>`, `provider:<name>:invalid_keys`
  - phase6-api: `alert:<marker>`, `session:<marker>`, `github:webhook:<delivery>`
  - zc: application-specific cache keys
- **Migrations:** None
- **Retention:** TTL-based (alerts: 86400s, sessions: 60s)
- **Backup:** Redis RDB/AOF (Docker volume `redis_data`)
- **Restore:** Standard Redis restore
- **PII classification:** Low (session markers, alert markers, webhook delivery IDs)
- **Tenant ownership:** None (shared key-value store)
- **Deletion semantics:** TTL expiry
- **Encryption:** None at rest (Docker volume)
- **Indexing:** Redis native
- **Observability:** None currently exposed

### 3. ZC data volume

- **Owner:** `services/zc`
- **Location:** Docker volume `zc_data` (path `/data` in container)
- **Schema:** Application-specific (uploads, logs, cache)
- **Migrations:** None
- **Retention:** Application-managed
- **Backup:** Docker volume backup
- **Restore:** Docker volume restore
- **PII classification:** Unknown — audit required
- **Tenant ownership:** Unknown — audit required
- **Deletion semantics:** Unknown — audit required
- **Encryption:** None at rest
- **Indexing:** Unknown
- **Observability:** Unknown

### 4. Zarvis local file stores

- **Owner:** `services/zarvis-memory`, `services/zarvis-perception`, `services/zarvis-action-gateway`, `services/zarvis-proactive`, `services/zarvis-task-gateway`, `services/zarvis-orchestrator`
- **Location:** Local file system under `./data/zarvis-*` or `env.ZARVIS_*_DATA_DIR`
- **Schema:** Encrypted JSON files (memory, perception), action logs, task plans, session journals
- **Migrations:** None
- **Retention:** Indefinite
- **Backup:** File system backup
- **Restore:** File system restore
- **PII classification:** High (owner-only encrypted memory, perception sessions, commands)
- **Tenant ownership:** Single-owner (`owner-4076926`)
- **Deletion semantics:** Manual or cleanup API
- **Encryption:** At-rest encryption via `EncryptedMemoryStore` and `EncryptedPerceptionStore` with master keys
- **Indexing:** In-memory
- **Observability:** Stdout audit logs

### 5. Supabase (phase6-api)

- **Owner:** `services/phase6-api`
- **Location:** External Supabase project (URL configured via `SUPABASE_URL`)
- **Schema:** Single allowlisted table (`SUPABASE_TABLE`)
- **Migrations:** External (Supabase)
- **Retention:** Unknown
- **Backup:** Supabase-managed
- **Restore:** Supabase-managed
- **PII classification:** Unknown — depends on table content
- **Tenant ownership:** None (read-only bridge)
- **Deletion semantics:** None (read-only)
- **Encryption:** TLS in transit; Supabase-managed at rest
- **Indexing:** Supabase-managed
- **Observability:** None

## Shared database concerns

- No shared PostgreSQL or MySQL database is currently used by platform services.
- `phase6-api` uses Redis as its primary store.
- `agent-provider` uses file-based JSON.
- Zarvis services use encrypted file stores.
- `zc` uses Redis and file uploads.
- **Risk:** File-based stores do not provide ACID guarantees, concurrent access safety, or query capabilities. If any service grows beyond single-writer patterns, a migration to a proper database will be required.

## Data ownership gaps

1. **zc** data volume contents and retention policy are undocumented.
2. **Supabase** table schema, PII classification, and retention are undocumented.
3. **Agent provider** JSON store lacks per-tenant deletion semantics.
4. No **encryption at rest** for ai-gateway Redis key pools or phase6-api Redis data.
