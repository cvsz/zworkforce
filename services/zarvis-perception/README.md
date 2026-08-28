# Z.A.R.V.I.S. Consent-Based Perception

Owner-only, one-shot image/document/screen/camera analysis for Epic #148 / Issue #153.

## Invariants

- The owner is permanently `github:4076926` in tenant `owner-4076926`.
- Media cannot be analyzed before exact purpose/modality consent.
- Screen and camera capture are one-shot browser snapshots; media tracks are stopped immediately.
- No continuous or hidden capture exists.
- Raw media is processed in memory and never persisted.
- Only encrypted redacted analysis and provenance are retained.
- Untrusted media cannot alter policy, grant tools, approve actions, or execute commands.
- Biometric identification is not implemented.

## Configuration

```bash
export ZARVIS_EDGE_SHARED_SECRET='<at-least-32-random-bytes>'
export ZARVIS_PERCEPTION_WORKER_TOKEN='<independent-32-byte-token>'
export ZARVIS_PERCEPTION_MASTER_KEY_B64="$(openssl rand -base64 32)"
export ZARVIS_PERCEPTION_DATA_DIR='/var/lib/zarvis-perception'
pnpm --filter @z-platform/zarvis-perception start
```

## API

- `GET /healthz`
- `GET/POST /v1/perception/sessions`
- `GET/DELETE /v1/perception/sessions/{session_id}`
- `POST /v1/perception/sessions/{session_id}/activate`
- `POST /v1/perception/sessions/{session_id}/stop`
- `POST /v1/perception/sessions/{session_id}/media`
- `POST /v1/internal/perception/purge-expired`

Deletion requires `x-zarvis-confirm-delete: <session_id>`. The internal purge route requires a separate worker bearer token.

## Local analyzer

The first adapter supports:

- UTF-8 text: secret/PII redaction, prompt-injection neutralization, excerpt and word count;
- simple PDF: signature validation, bounded printable-text extraction, then the same redaction pipeline;
- PNG/JPEG: signature and bounded dimension extraction.

The output always marks content as untrusted, sets `policy_effect: none`, returns an empty tool-grant list, and reports `raw_media_retained: false`.

Future provider-backed vision/document analyzers must remain behind the same owner consent, redaction, provenance, retention, and deletion boundaries. Provider credentials must remain server-side.
