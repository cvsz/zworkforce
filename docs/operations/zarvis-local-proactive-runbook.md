# Z.A.R.V.I.S. Local Proactive Operations Runbook

## Install

```bash
bash scripts/zarvis-local-setup.sh
```

The installer preserves existing local secrets, adds a separate proactive-worker token when missing, starts the local stack, and waits for both loopback services.

## Smoke test

1. Open `http://127.0.0.1:8099`.
2. Unlock with `ZARVIS_LOCAL_OWNER_TOKEN`.
3. Set timezone, quiet hours, daily budget, cooldown, and confidence threshold.
4. Create the `zarvis-action-gateway` local health schedule.
5. Confirm a healthy check creates an evaluation but no unhealthy notification.
6. Stop the action gateway temporarily and run one worker tick.
7. Confirm the inbox explains the unhealthy result and source.
8. Create an approval handoff and verify `requires_owner_approval: true` and `executed: false`.
9. Record feedback and revoke the schedule.

## Verify local isolation

```bash
ss -ltnp | grep -E ':8098|:8099'
curl --fail http://127.0.0.1:8099/healthz
```

Both sockets must be loopback only. LAN access must fail.

## Worker

The local worker calls only:

```text
POST /v1/internal/proactive/tick
x-zarvis-proactive-worker-token: <independent-token>
```

The worker has no owner or action credential.

## Backup and restore

Back up `zarvis_proactive_data` separately from `.env.zarvis.local`:

```bash
docker run --rm -v zarvis_proactive_data:/data -v "$PWD":/backup alpine \
  tar -C /data -czf /backup/zarvis-proactive-data.tgz .
```

Restore only while proactive service and worker are stopped. After restore, verify policy, subscriptions, prior notification decisions, feedback, and handoff state.

## Rotation

1. Stop the proactive worker.
2. Generate a new proactive-worker token.
3. Replace only `ZARVIS_PROACTIVE_WORKER_TOKEN` in `.env.zarvis.local`.
4. Restart proactive service and worker.
5. Confirm the old worker token receives 403 and the new token can tick.

Owner-token rotation requires restarting all owner-facing local services together.

## Incident response

Revoke all subscriptions from the owner console, stop the proactive worker, preserve `proactive-events.jsonl` if investigation is required, rotate the worker token, review suppression/delivery decisions, and restore from a trusted backup when journal integrity is uncertain.
