# Z.A.R.V.I.S. Local Action Operations Runbook

## Install on Ubuntu/Linux

```bash
bash scripts/zarvis-local-setup.sh
```

The script creates `.env.zarvis.local` with mode `0600`, generates independent owner/worker tokens, starts the gateway and worker, and waits for health.

Console: `http://127.0.0.1:8098`

## Verify isolation

```bash
ss -ltnp | grep 8098
curl --fail http://127.0.0.1:8098/healthz
curl --fail http://$(hostname -I | awk '{print $1}'):8098/healthz && exit 1 || true
```

The listening socket must be loopback only and LAN access must fail.

## Normal smoke test

1. Unlock with `ZARVIS_LOCAL_OWNER_TOKEN`.
2. Preview `assistant.response_style = concise`.
3. Verify previous value, next value, no network access, and no external side effects.
4. Approve the exact preview.
5. Wait for the local worker to mark it `executed`.
6. Roll back and verify status `rolled_back`.

## Emergency stop

Use the red emergency-stop control. It persists stop state, revokes pending and approved actions, and prevents new preview/execution. Resume requires the exact confirmation `RESUME_LOCAL_ACTIONS`.

## Backup and restore

Back up the Docker volume separately from `.env.zarvis.local`:

```bash
docker run --rm -v zarvis_action_data:/data -v "$PWD":/backup alpine \
  tar -C /data -czf /backup/zarvis-action-data.tgz .
```

Restore only while both services are stopped. After restore, verify one historical action and perform a preview/rollback smoke test.

## Rotation

1. Activate emergency stop.
2. Stop Compose.
3. Generate new owner and worker tokens independently.
4. Replace values in `.env.zarvis.local` and keep mode `0600`.
5. Start Compose and verify old tokens fail.
6. Resume local actions explicitly.

## Incident response

Stop the worker first, activate emergency stop if the gateway remains available, stop Compose, preserve `action-events.jsonl` for investigation, rotate both tokens, inspect `local-state.json`, and restore only from a trusted backup when state integrity is uncertain.
