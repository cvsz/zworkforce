# Z.A.R.V.I.S. First-Slice Runbook

## Start locally

Use two terminals from the repository root.

```bash
pnpm --filter @z-platform/zarvis-orchestrator start
```

```bash
ZARVIS_ORCHESTRATOR_URL=http://127.0.0.1:8094 \
  pnpm --filter @z-platform/zarvis-console start
```

Open `http://127.0.0.1:8095`.

## Optional GitHub authorization

Public repositories can use unauthenticated GitHub REST requests. For private repositories or higher rate limits, inject `GITHUB_TOKEN` into the orchestrator process only:

```bash
GITHUB_TOKEN='set-through-your-secret-manager' \
  pnpm --filter @z-platform/zarvis-orchestrator start
```

Never place the token in browser environment variables, static files, command payloads, or repository configuration.

## Health checks

```bash
curl --fail http://127.0.0.1:8094/healthz
curl --fail http://127.0.0.1:8095/healthz
```

## Command smoke test

```bash
curl --fail \
  -H 'content-type: application/json' \
  -d '{
    "schema_version":"zarvis.command.requested.v1",
    "session_id":"smoke-1",
    "input":{
      "modality":"text",
      "text":"ตรวจสถานะ GitHub cvsz/z-platform",
      "locale":"th-TH"
    }
  }' \
  http://127.0.0.1:8094/v1/commands
```

Expected properties:

- HTTP 200.
- `status` is `completed`.
- `intent.name` is `github.repository.status`.
- `speech.text` is non-empty.
- `audit.event_id` is present.
- Orchestrator logs one JSON audit event with `tool.access` set to `read_only`.

## Failure handling

| Symptom | Check | Action |
|---|---|---|
| `repository_not_found` | Repository spelling and token access | Correct owner/repo or grant read access |
| `github_authorization_failed` | Token validity or rate limit | Rotate token or wait for rate reset |
| `github_timeout` | Network and GitHub status | Retry after checking egress and upstream health |
| `unsupported_intent` | Transcript contains a recognizable owner/repo | Use `ตรวจสถานะ GitHub owner/repo` or explicit tool arguments |
| Console returns 502 | Orchestrator health | Restore `services/zarvis-orchestrator` and verify configured URL |

## Emergency stop

Stop or scale the orchestrator to zero. The console has no direct GitHub capability and cannot execute the tool without the orchestrator.
