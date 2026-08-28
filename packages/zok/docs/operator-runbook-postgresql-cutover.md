# Operator Runbook: Application-Wide JSON-to-PostgreSQL Cutover

## Overview

This runbook documents the end-to-end procedure for migrating Zok's application data from JSON file storage (`server/db.json`) to PostgreSQL. The migration is a P0 blocker and must follow the canary procedure documented below.

**Scope:** `chats`, `campaigns`, `integrations`, `aiConfig`, `flowNodes`, `syncLogs`

---

## Pre-flight Checklist

Execute every step before beginning the canary procedure.

### 1. Backups

- [ ] Snapshot the PostgreSQL database:
  ```bash
  pg_dump -Fc -U <app_user> -d <database_name> -f /tmp/zok-pg-backup-$(date +%Y%m%d%H%M).dump
  ```
- [ ] Copy `server/db.json` to a timestamped backup:
  ```bash
  cp server/db.json /tmp/zok-json-backup-$(date +%Y%m%d%H%M).json
  ```
- [ ] Verify backup integrity:
  ```bash
  pg_restore -l /tmp/zok-pg-backup-*.dump | tail -n 5
  ```

### 2. PostgreSQL Readiness

- [ ] Confirm `ZOK_POSTGRES_URL` is set in the application environment.
- [ ] Confirm `ZOK_ADMIN_TENANT_ID` is set (required for migration ownership).
- [ ] Confirm the `tenants` table contains the admin tenant row.
- [ ] Confirm the following tables exist and are empty of tenant data:
  - `campaigns`
  - `integrations`
  - `ai_config`
  - `flow_nodes`
  - `sync_logs`
  - `zok_cutover_idempotency`
- [ ] Confirm `contacts`, `conversations`, and `messages` tables are empty or contain only data from previous test runs.

### 3. Feature Flags

- [ ] Set `ZOK_CHAT_STORAGE=json` in the application environment to keep the application on JSON storage during cutover.
- [ ] Confirm the feature flag for PostgreSQL chat routing is **disabled**:
  ```bash
  grep -q "ZOK_CHAT_STORAGE=postgres" /proc/$(pgrep -f 'node server.js')/environ || echo "OK: JSON mode active"
  ```

### 4. Rehearsal Validation

- [ ] Run the rehearsal script in dry-run mode to confirm zero drift:
  ```bash
  node scripts/rehearse-application-cutover.js \
    --source server/db.json \
    --tenant "$ZOK_ADMIN_TENANT_ID" \
    --postgres-url "$ZOK_POSTGRES_URL"
  ```
  Expected output: `"ready": true`, `"driftCount": 0`

---

## Canary Procedure

The cutover proceeds in four traffic stages. At each stage, verify metrics before advancing.

### Stage 1: 1% Traffic

1. Deploy with `ZOK_CHAT_STORAGE=postgres` to 1% of instances or enable PostgreSQL routing for 1% of requests.
2. Run verification commands:
   ```bash
   # Verify PostgreSQL row counts match JSON
   node scripts/rehearse-application-cutover.js \
     --source server/db.json \
     --tenant "$ZOK_ADMIN_TENANT_ID" \
     --postgres-url "$ZOK_POSTGRES_URL"
   ```
   ```sql
   SELECT 'campaigns' AS table_name, count(*) FROM campaigns WHERE tenant_id = '<tenant_id>'
   UNION ALL
   SELECT 'integrations', count(*) FROM integrations WHERE tenant_id = '<tenant_id>'
   UNION ALL
   SELECT 'ai_config', count(*) FROM ai_config WHERE tenant_id = '<tenant_id>'
   UNION ALL
   SELECT 'flow_nodes', count(*) FROM flow_nodes WHERE tenant_id = '<tenant_id>'
   UNION ALL
   SELECT 'sync_logs', count(*) FROM sync_logs WHERE tenant_id = '<tenant_id>';
   ```
3. Monitor application logs for 5 minutes. Look for:
   - `PostgreSQL chat import is incomplete`
   - `Database is unavailable`
   - Connection pool exhaustion errors
4. **Rollback trigger:** If error rate exceeds 0.1% or latency p99 increases by >50%, execute the Rollback Procedure (below) and stop.

### Stage 2: 10% Traffic

1. Increase PostgreSQL routing to 10%.
2. Repeat verification commands from Stage 1.
3. Monitor for 15 minutes.
4. **Rollback trigger:** Same as Stage 1.

### Stage 3: 50% Traffic

1. Increase PostgreSQL routing to 50%.
2. Repeat verification commands.
3. Monitor for 30 minutes.
4. **Rollback trigger:** Same as Stage 1.

### Stage 4: 100% Traffic

1. Set `ZOK_CHAT_STORAGE=postgres` on all instances.
2. Run verification commands.
3. Monitor for 60 minutes.
4. Celebrate.

---

## Rollback Triggers

Execute the Rollback Procedure if ANY of the following occur during any canary stage:

- HTTP 5xx error rate exceeds 0.1% of total requests
- p99 latency increases by >50% compared to baseline
- `rehearse-application-cutover.js` reports non-zero drift that cannot be reconciled within 5 minutes
- PostgreSQL connection pool exhaustion (`pool limit reached` in logs)
- Any `RLS policy violation` or `foreign key constraint` errors in application logs
- Unplanned PostgreSQL maintenance or failover

---

## Rollback Procedure

**RPO Target:** < 5 minutes of data loss
**RTO Target:** < 2 minutes to restore JSON mode

1. **Immediate actions:**
   ```bash
   # Revert to JSON storage on all instances
   export ZOK_CHAT_STORAGE=json
   # Restart application
   pm2 restart all  # or equivalent
   ```

2. **Verify JSON rollback:**
   ```bash
   curl -s http://localhost:3005/api/health | jq .
   curl -s http://localhost:3005/api/db | jq '.chats | length'
   ```

3. **Restore PostgreSQL from backup if data was corrupted:**
   ```bash
   pg_restore -U <app_user> -d <database_name> /tmp/zok-pg-backup-*.dump
   ```

4. **Post-rollback reconciliation:**
   - Compare `server/db.json` against the pre-cutover backup.
   - If drift is detected, restore `server/db.json` from the timestamped backup.
   - Run `node scripts/rehearse-application-cutover.js --dry-run` against a fresh PostgreSQL database to confirm the cutover path is still valid.

---

## RPO / RTO Targets

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **RPO** | < 5 minutes | Time between last successful JSON write and the PostgreSQL snapshot taken at pre-flight. Measured by comparing `updated_at` timestamps on migrated rows vs. `db.json` mtime. |
| **RTO** | < 2 minutes | Time from rollback trigger to `ZOK_CHAT_STORAGE=json` serving traffic again. Measured by stopwatch from incident declaration to successful `/api/health` response in JSON mode. |
| **Drift tolerance** | 0 records | `rehearse-application-cutover.js` must report `"driftCount": 0` at each stage. |

---

## Verification Commands

### Pre-flight

```bash
# 1. JSON database health
node -e "console.log(JSON.parse(require('fs').readFileSync('server/db.json','utf8')).chats.length, 'chats in JSON')"

# 2. PostgreSQL connectivity
node -e "
  const { Client } = require('pg');
  const client = new Client({ connectionString: process.env.ZOK_POSTGRES_URL });
  client.connect().then(() => client.query('SELECT 1')).then(() => console.log('PostgreSQL OK')).catch(e => { console.error(e); process.exit(1); });
"

# 3. Rehearsal dry-run
node scripts/rehearse-application-cutover.js \
  --source server/db.json \
  --tenant "$ZOK_ADMIN_TENANT_ID" \
  --postgres-url "$ZOK_POSTGRES_URL"
```

### Stage Verification (1%, 10%, 50%, 100%)

```bash
# Row counts per collection
node -e "
  const { Client } = require('pg');
  const client = new Client({ connectionString: process.env.ZOK_POSTGRES_URL });
  client.connect();
  client.query(\"SET app.tenant_id = '\${process.env.ZOK_ADMIN_TENANT_ID}'\");
  const tables = ['campaigns','integrations','ai_config','flow_nodes','sync_logs'];
  for (const t of tables) {
    const r = await client.query('SELECT count(*) FROM ' + t);
    console.log(t, r.rows[0].count);
  }
  await client.end();
"
```

```bash
# Rehearsal comparison
node scripts/rehearse-application-cutover.js \
  --source server/db.json \
  --tenant "$ZOK_ADMIN_TENANT_ID" \
  --postgres-url "$ZOK_POSTGRES_URL"
```

---

## Emergency Contacts and Escalation

| Role | Contact | When to Escalate |
|------|---------|-----------------|
| **On-call Platform Engineer** | #platform-oncall (Slack) | Any rollback trigger fires |
| **Database Administrator** | dba@zok.zeaz.dev | PostgreSQL connectivity or corruption |
| **Engineering Manager** | em@zok.zeaz.dev | Incident declared; RTO at risk |
| **Product Manager** | pm@zok.zeaz.dev | Customer-facing impact or feature flag decision |

**Escalation path:**
1. Platform engineer investigates and executes rollback within 5 minutes.
2. If rollback fails or RTO is breached, escalate to DBA + Engineering Manager.
3. If customer impact is confirmed, notify Product Manager within 15 minutes.

---

## Idempotency Keys

The cutover uses the `zok_cutover_idempotency` table to prevent duplicate records:

| Collection | External ID Format |
|------------|-------------------|
| `campaigns` | `campaign:<name>` |
| `integrations` | `integration:<json_id>` |
| `aiConfig` | `ai_config:singleton` |
| `flowNodes` | `flow_node:<json_id>` |
| `syncLogs` | `sync_log:<index>:<hash>` |

If a record already exists in `zok_cutover_idempotency`, the migration script skips it. To force re-migration of a specific collection, delete its idempotency keys:

```sql
DELETE FROM zok_cutover_idempotency WHERE collection = 'campaigns';
```

---

## Appendix: Rehearsal Script Reference

```bash
# Dry-run (default)
node scripts/rehearse-application-cutover.js \
  --source server/db.json \
  --tenant "$ZOK_ADMIN_TENANT_ID" \
  --postgres-url "$ZOK_POSTGRES_URL"

# Apply migration
node scripts/rehearse-application-cutover.js \
  --source server/db.json \
  --tenant "$ZOK_ADMIN_TENANT_ID" \
  --postgres-url "$ZOK_POSTGRES_URL" \
  --apply
```

**Exit codes:**
- `0` — success (dry-run with zero drift, or apply completed)
- `1` — fatal error (invalid arguments, connection failure)
- `2` — dry-run detected drift
