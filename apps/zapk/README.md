# ZEAZ APK Hub — independent APK catalogue starter

Built as an independent proof-of-concept, not a clone of APKCube source code, content, or brand.

## Run with Docker

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
# Set *different* random ZEAZ_ADMIN_TOKEN and ZEAZ_SIGNING_SECRET values in .env

docker compose up --build -d
curl http://127.0.0.1:8000/api/health
```

Open http://127.0.0.1:8000 (and /docs for API explorer). The Docker Compose port is loopback-only; configure your own HTTPS reverse proxy for remote access.

## Run without Docker

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export ZEAZ_ADMIN_TOKEN=$(python -c 'import secrets;print(secrets.token_urlsafe(48))')
export ZEAZ_SIGNING_SECRET=$(python -c 'import secrets;print(secrets.token_urlsafe(48))')
uvicorn app.main:app --reload
pytest -q
```

## Publisher workflow (use only apps you have permission to distribute)

```bash
curl -X POST http://127.0.0.1:8000/api/publisher/apps \
  -H "Authorization: Bearer $ZEAZ_ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"package":"dev.example.hello","name":"Hello","developer":"Example","category":"Tools"}'
curl -X POST http://127.0.0.1:8000/api/publisher/apps/dev.example.hello/builds \
  -H "Authorization: Bearer $ZEAZ_ADMIN_TOKEN" \
  -F 'version=1.0.0' -F 'file=@./hello.apk'
```

## Functional scope
- Responsive app/game catalogue, categories, search, detail, release history
- Google Play URL/package resolver (metadata lookup only; not a Google Play downloader)
- Publisher listing and archive upload with admin bearer token
- SHA-256 calculation/lookup, time-limited HMAC download links
- OpenAPI explorer
- Optional APKCube catalogue search proxy using paid official API; key remains server-side

## Not implemented / release blockers
- No direct Google Play APK acquisition, scraping, or bulk mirroring
- No malware analysis, Android signing verification, package manifest validation, SDK/tracker detection, device-targeted bundle generation or actual APKS install flow
- No MFA, publisher identity verification, content review, ownership checks or abuse/takedown console
- No object storage/CDN, upload quarantine, distributed rate limiting, WAF, metrics, monitoring, billing, MCP, or production security approval
- ZIP magic validation is *not* sufficient for trusting uploaded APKs. Until a proper scanning and signature-validation pipeline exists, keep publisher uploads restricted and do not offer general-public distribution.
- Admin token is single-tenant bootstrap only; replace with RBAC, audit trails and per-publisher authorization before multi-tenant usage.
- Data stored on a local SQLite volume. Add PostgreSQL, S3-compatible storage, backups and DR for production.

## Suggested phase 2
PostgreSQL+Redis+S3/MinIO, ClamAV and Android package validation, apk signing lineage and SHA-256 comparison, publisher attestation, rate limiting, signed webhooks, queue workers, observability, OpenAPI clients, MCP gateway, quotas and billing, SEO pages, moderation and takedown workflow, upload scan gates with quarantine.
