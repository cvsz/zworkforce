# Kids Factory Operator Runbook

Scope: offline-capable vertical slices 1–7 on the zWorkforce control plane.
Production promotion additionally needs the external evidence listed in
`TEST-EVIDENCE.md` (real providers, YouTube OAuth, S3/Qdrant, OTLP, signing).

## 1. Health checks

```bash
python3 -m zworkforce doctor
PYTHONPATH=. python3 -m unittest discover -s tests -p "test_kids_factory.py"
```

`doctor` must exit 0. The kids suite must be 27/27 green. Anything else is
a NO-GO for demo use, let alone production.

## 2. Common incidents

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Render job `failed` | Bad preset, missing scenes/timeline, FFmpeg error | Read `job.error`; fix input; `POST .../render-jobs/{id}/retry` or re-queue; after 3 tick attempts it dead-letters — inspect, do not blindly retry publish paths |
| Publishing `400` on `/publish` | No approved approval for the episode | Request approval, get human `approve`, prepare a publishing job bound to that approval id, then publish |
| `slot_conflict` (409) | Channel double-booked | Pick another `slot_at`; cancel the stale slot first if it was a mistake |
| `budget/quota exceeded` (400) | Episode budget or brand quota too low | Raise `budget_credits`/quota via an authorized brand/episode update, or reduce scope; never edit `kids_usage` rows by hand |
| Safety `blocked` | Dangerous imitation or third-party IP hint | Rewrite the content with original designs; re-run pipeline; safety passing still needs human approval |
| Duplicate-upload scare | Network retry after `/publish` | Reuse the same `Idempotency-Key`; mock external ids are deterministic per key — verify via `GET .../publishing?episode_id=` before acting |

## 3. Backup

1. Export every active episode: `GET /api/v1/kids/episodes/{id}/export` → store JSON (it carries `format: kids-export-1`).
2. Back up the artifact directory (`data/kids-renders/...` plus the content-addressed store) alongside the JSON.
3. Back up the database with the operator's standard procedure (SQLite file copy with WAL checkpoint, or managed PostgreSQL snapshot/PITR). Record snapshot id, UTC time, and SHA-256 of the export files.

## 4. Restore drill

1. On an isolated target (never production first): `POST /api/v1/kids/episodes/import` with `{"bundle": <export>, "id": "<new-id>"}`.
2. Verify counts in the response (`scripts/scenes/timelines/assets/music`) match the export.
3. Re-run `POST .../episodes/<new-id>/pipeline`; confirm it reaches `approval_request` without `failed`.
4. Confirm approvals show as `pending` (they must NOT transfer) and publishing stays blocked until a fresh human approval.
5. Record operator, timestamps, commands, and results. A drill without this record does not count as evidence.

## 5. Rollback

The slice is additive. To disable: stop traffic, drop the `kids_*` tables,
remove the `/api/v1/kids/*` and `kids.*` wiring, and redeploy the previous
image. No existing control-plane data is rewritten by the slice, so rollback
does not require data migration. The rollback target for any release remains
the last immutable tag per `docs/PRODUCTION-EVIDENCE.md`.

## 6. Escalation

Security findings (secret in logs, cross-tenant leak, auth bypass) → freeze
the branch, do not merge, open a security thread, and notify the release
authority. Feature bugs → file an issue with tenant (redacted), episode id,
request id, and UTC timestamp. Never paste secrets, tokens, or export bundles
containing internal names into public threads.
