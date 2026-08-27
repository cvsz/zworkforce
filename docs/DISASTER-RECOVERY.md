# Disaster Recovery

This runbook covers repository-supported recovery of zWorkforce application state. It does not replace managed PostgreSQL, object-store or identity-provider disaster-recovery procedures.

## Recovery objectives

Operators must define environment-specific targets before go-live:

| Objective | Required value |
|---|---|
| RPO | Maximum acceptable data loss |
| RTO | Maximum acceptable service outage |
| Backup retention | Number of retained restore points |
| Restore test cadence | Recommended at least quarterly |
| Artifact/vector-store recovery | Provider-specific policy |

## Data inventory

Critical state can exist in multiple systems:

- PostgreSQL: tenants, agents, tasks, workflows, approvals, events, schedules, evaluation, FinOps, audit and configuration state.
- Artifact backend: local volume or S3-compatible object storage.
- Semantic memory: local database/vector state or Qdrant.
- External secrets: Vault, AWS Secrets Manager or mounted secret provider.
- External observability: OTLP/metrics/log backends.

Back up each configured backend independently. A PostgreSQL dump does not back up S3/Qdrant/Vault.

## PostgreSQL backup

Use a dedicated backup role with sufficient read privileges and an encrypted backup destination.

```bash
export ZWORKFORCE_BACKUP_DATABASE_URL='postgresql://backup-user:...@session-pooler:5432/zworkforce?sslmode=require'
bash scripts/backup-postgres.sh
```

Use a direct or session-pooler URL for the backup connection; transaction
poolers (`6543`) are not a backup endpoint. The script places the URL in a
short-lived mode-0600 libpq service file, so it is not passed as a
`pg_dump` process argument. It writes a PostgreSQL custom-format dump, validates
its catalog with `pg_restore --list`, then writes a SHA-256 sidecar. A backup
that cannot be parsed is not accepted.

For managed PostgreSQL, use provider-native PITR/snapshot backups in addition to logical dumps.

## Restore drill

Never test a restore against the live production database.

1. Provision an isolated PostgreSQL instance.
2. Stop zWorkforce API/workers/scheduler/outbox for the target environment.
3. Set the target `ZWORKFORCE_RESTORE_DATABASE_URL` to a direct or session-pooler URL.
4. Verify the backup checksum.
5. Explicitly authorize the destructive restore:

```bash
export ZWORKFORCE_RESTORE_CONFIRM=YES
bash scripts/restore-postgres.sh backups/zworkforce-YYYYMMDDTHHMMSSZ.dump
```

6. Run:

```bash
zworkforce doctor
ZWORKFORCE_BASE_URL=http://127.0.0.1:9569 bash scripts/smoke-test.sh
```

7. Validate representative tenants, agents, workflows, schedules, approval state and recent audit/task history.
8. Record achieved RPO/RTO and any manual steps.

## Production database loss

1. Declare the incident and freeze mutating traffic.
2. Stop API, workers, scheduler and outbox or scale them to zero.
3. Preserve failed database/storage evidence before overwrite when possible.
4. Select the newest known-good restore point consistent with the declared RPO.
5. Restore PostgreSQL/PITR first.
6. Restore artifact/vector backends to a time compatible with the database restore point.
7. Rotate credentials if compromise is suspected.
8. Run database/application validation and smoke tests.
9. Resume scheduler/outbox, then workers, then API traffic.
10. Monitor dead letters, duplicate integration deliveries, provider state and SLOs closely.

## Rollback without database loss

For application regressions where data is healthy:

1. Stop new deployments.
2. Roll back to the previous immutable image digest/tag.
3. Do not restore the database unless the incident explicitly requires data rollback.
4. Run `zworkforce doctor` and smoke tests.
5. Confirm workers can reclaim expired leases and schedulers/outbox retain single active leaders.

## Region or cluster loss

The repository is compatible with external HA/PITR/multi-region designs but does not provision them automatically. Recovery must restore or promote:

- PostgreSQL primary/replica;
- artifact and vector backends;
- secret/identity dependencies;
- ingress/DNS;
- observability destinations.

After failover, verify network allowlists and callback/webhook/OIDC URLs because these are commonly region-specific.

## Evidence to retain

For every drill or incident retain:

- release commit/tag/image digest;
- selected backup ID/checksum and timestamp;
- RPO/RTO achieved;
- restore/smoke-test output;
- credential rotations;
- missing or duplicated external side effects;
- corrective actions and owners.
