# Z.A.R.V.I.S. Local Release Runbook

Issue: #156  
Target: one Ubuntu/Linux host or VM owned by GitHub user ID `4076926`

## Supported topology

- user-facing ports bind only to loopback;
- no Cloudflare, reverse proxy, public DNS, port forwarding, or LAN ingress;
- Action Console: `http://127.0.0.1:8098`;
- Proactive Console: `http://127.0.0.1:8099`;
- independent owner, action-worker, and proactive-worker credentials;
- fixed named volumes `zarvis_action_data` and `zarvis_proactive_data`;
- read-only container root filesystems, dropped Linux capabilities, no-new-privileges, PID/file-descriptor/CPU/memory limits.

## Install or upgrade

```bash
bash scripts/zarvis-local-setup.sh
```

Keep `.env.zarvis.local` at mode `0600`. The installer preserves existing secrets and adds missing settings without rotating credentials silently.

## Automated release validation

Run the release workflow locally where practical or invoke GitHub Actions workflow **ZARVIS Local Release**. It performs:

1. focused contracts/action/proactive regression tests;
2. hardened Compose validation and deployment;
3. loopback and container-resource verification;
4. action preview, approval, execution, rollback, emergency revoke, and resume;
5. proactive schedule, explainable notification, feedback, revoke, and non-executing handoff;
6. bounded latency/error sampling;
7. security red-team suite;
8. worker interruption and service restart drill;
9. volume backup, destructive volume removal, restore, and state verification;
10. independent credential rotation and rejection of old credentials;
11. evidence secret scan, SHA-256 manifest, artifact upload, and main-branch provenance attestation.

## Backup

```bash
bash scripts/zarvis-local-backup.sh ./zarvis-local-backup
```

The backup contains durable action/proactive data only. `.env.zarvis.local` is intentionally excluded and must be protected separately.

## Restore

Stop the stack before restoring:

```bash
docker compose --env-file .env.zarvis.local -f compose.zarvis-local.yml down
bash scripts/zarvis-local-restore.sh ./zarvis-local-backup
bash scripts/zarvis-local-setup.sh
```

After restore, run owner acceptance and confirm historical action, notification, feedback, revocation, and handoff state.

## Credential rotation

1. Activate action emergency stop.
2. Stop both workers.
3. Generate three independent values with `openssl rand -hex 32`.
4. Replace owner, action-worker, and proactive-worker values in `.env.zarvis.local`.
5. Recreate all four local services.
6. Verify all old credentials return 403 and all new credentials succeed only at their intended boundary.
7. Resume local actions using the exact confirmation.

## Incident response

1. Stop both workers.
2. Activate emergency stop if the action gateway remains trustworthy.
3. Revoke proactive subscriptions.
4. Stop the local stack.
5. Preserve fixed journals and the current evidence manifest when investigation is required.
6. Rotate all credentials.
7. Verify backup hashes before restore.
8. Run red-team, restart, restore, rotation, and owner acceptance again before reopening the consoles.

## Rollback

Application rollback means checkout of the last accepted release SHA followed by Compose recreation. Durable state is backward-preserved only when the release notes explicitly state compatibility. Never restore a data archive without its matching manifest and operator-reviewed version compatibility.
