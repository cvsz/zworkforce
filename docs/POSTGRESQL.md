# PostgreSQL distributed runtime

Set:

```env
ZWORKFORCE_DATABASE_URL=postgresql://user:password@host:5432/zworkforce
```

The repository automatically selects PostgreSQL based on URI scheme. psycopg executes parameterized statements through a compatibility layer so the same repository mixins serve SQLite and PostgreSQL.

## Supabase HA endpoint

For long-running HA VMs, use one shared Supabase session-pooler URL and inject
the password from the external secret manager:

```env
ZWORKFORCE_DATABASE_URL=postgresql://postgres.<project-ref>:<url-encoded-password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

Use the session pooler (`5432`) for VM services and `pg_dump`/`pg_restore`.
Transaction-pooler URLs (`6543`) are intended for short-lived transactions and
are not the repository's backup endpoint. `zwf-api.zeaz.dev` is an HTTPS API
hostname; it must never be used as the PostgreSQL host.

## Queue semantics

PostgreSQL workers claim with:

```sql
SELECT *
FROM tasks2
WHERE status='queued'
  AND cancel_requested=0
  AND run_after<=now_value
ORDER BY priority DESC, created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

The selected row is transitioned to `running`, attempt count increments and a lease owner/expiry/heartbeat is recorded before commit.

## Production recommendations

- Require TLS for non-local DB connections.
- Use managed HA or equivalent streaming-replication/failover architecture.
- Enable automated backups and PITR.
- Monitor storage growth in tasks, events, audit and usage ledgers.
- Use connection pooling/proxying when API/worker counts become large; v3 opens short-lived repository connections by design.
- Keep application and database clocks synchronized.

## Migration

Schema initialization applies additive v4 columns for workflow occurrence keys
and outbox claims to existing databases. SQLite-to-PostgreSQL data migration is
not automatic or repository-supported. The default production posture is a
fresh PostgreSQL database; if an existing SQLite deployment contains data,
production promotion is blocked until a separately approved export/import
procedure freezes writes, preserves all tenant-scoped state, verifies table
counts and audit chains, and records the cutover.
