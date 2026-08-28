# Z.A.R.V.I.S. Voice Session Bridge Runbook

## Preconditions

- PR quality gates pass.
- The identity edge allows only GitHub user ID `4076926`.
- The edge strips all incoming `x-zarvis-*` headers before injecting trusted values.
- ZVoice and the orchestrator origins are not directly public.
- `ZARVIS_EDGE_SHARED_SECRET` and `ZARVIS_ORCHESTRATOR_SERVICE_TOKEN` are independently generated and stored in the deployment secret manager.
- `ZARVIS_DATA_DIR` is mounted on persistent storage owned by the service account.

## Start order

1. Start the GitHub adapter dependencies, if a private repository token is required.
2. Start `zarvis-orchestrator` with the service token and data directory.
3. Verify `GET /healthz` reports `durable_sessions: true`.
4. Start voice-gateway and voice-agent.
5. Start ZVoice with `ZVOICE_ZARVIS_MODE=true`.
6. Verify ZVoice `/health` reports `zarvis_owner_mode: true` and `zarvis_bridge_configured: true`.

## Smoke test

Speak or submit:

```text
ตรวจสถานะ GitHub cvsz/z-platform
```

Verify:

- the user transcript appears once;
- the realtime model response is cancelled in Z.A.R.V.I.S. mode;
- the orchestrator returns a speech-ready repository summary;
- Browser TTS speaks the summary;
- `GET /v1/sessions/{session_id}` contains `command.accepted` and `command.completed`;
- repeating the same `command_id` returns `replayed: true` and does not add another tool audit event.

## Privacy deletion

Send `DELETE /v1/sessions/{session_id}` with:

```text
x-zarvis-confirm-delete: {session_id}
```

Confirm that the session event file and referenced command result envelopes are removed.

## Backup and recovery

- Stop the orchestrator or take a filesystem-consistent snapshot of `ZARVIS_DATA_DIR`.
- Encrypt backups at rest.
- Restrict restore access to the owner/operator identity.
- After restore, replay an existing `command_id` and confirm `replayed: true`.

## Emergency revocation

1. Disable the owner policy at the identity edge.
2. Rotate the edge shared secret.
3. Rotate the orchestrator service token.
4. Restart ZVoice and the orchestrator.
5. Revoke the GitHub token if compromise is suspected.
6. Review edge logs, audit events, and session events.
