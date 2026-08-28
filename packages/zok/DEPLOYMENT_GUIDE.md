# Zok Deployment Guide

This guide describes the supported Vite static client plus Express API deployment. It intentionally does not describe the legacy Next route artifacts as a production runtime.

## Prerequisites

- Node.js 22+ and npm.
- A TLS reverse proxy such as Caddy.
- An administrator email and PBKDF2 password hash.
- A writable private directory for the local JSON adapter during sandbox use.

## Configure

```bash
cd /mnt/zok
cp .env.example .env
node scripts/hash-password.mjs "replace-with-a-password-at-least-12-chars"
```

Set the generated value as `ZOK_ADMIN_PASSWORD_HASH` and set `ZOK_ADMIN_EMAIL`. In production set:

```env
NODE_ENV=production
PORT=3005
ZOK_DB_FILE=/var/lib/zok/db.json
ZOK_ALLOWED_ORIGINS=https://zok.zeaz.dev
ZOK_SESSION_TTL_MS=28800000
ZOK_ADMIN_EMAIL=admin@example.com
ZOK_ADMIN_PASSWORD_HASH=pbkdf2_sha256$...
```

Never commit `.env`, the password, session cookies, or `server/db.json`.

## Install and Verify

```bash
npm ci
npm test
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev --audit-level=high
```

All listed commands are release gates for this repository. The audit is limited to production dependencies; dev-tool warnings must still be reviewed before a Gold Master.

## Run the Services

For local development:

```bash
npm run dev
```

This starts the Vite dev server on `127.0.0.1:5175` and the Express API on `127.0.0.1:3005`.

For a production-shaped local run:

```bash
npm run build
NODE_ENV=production npm start
```

`npm start` runs the Vite preview server and API together for local verification. In production, use a process supervisor for `node server.js` and serve the already-built `dist/` directory from the reverse proxy.

## Caddy Reverse Proxy

Example site block:

```caddyfile
zok.zeaz.dev {
    encode zstd gzip

    @api path /api/*
    handle @api {
        reverse_proxy 127.0.0.1:3005
    }

    handle {
        root * /var/www/zok/dist
        try_files {path} /index.html
        file_server
    }
}
```

Keep the API bound to loopback. Configure the hostname in `ZOK_ALLOWED_ORIGINS` to match the browser origin exactly. Use HTTPS so production cookies have the `Secure` attribute.

## Health and Smoke Checks

The health endpoint is intentionally public and does not disclose credentials:

```bash
curl -fsS https://zok.zeaz.dev/api/health
```

Expected response shape:

```json
{"status":"ok","service":"zok-api","environment":"production"}
```

Without an authenticated session, data routes must return `401`. Without configured administrator credentials, protected routes must return `503`. These are expected fail-closed states.

## Storage and Scaling Boundary

`server/db.json` is an atomic, serialized local adapter for the sandbox. It is not suitable for multiple API instances, concurrent hosts, audit retention, customer data durability, or disaster recovery. Before horizontal scaling, replace it with:

1. PostgreSQL with versioned migrations and transaction boundaries.
2. Redis or another shared session/rate-limit store.
3. A durable queue for channel webhooks and broadcasts.
4. Encrypted backups with restore drills and a documented RPO/RTO.

## Security Controls in This Release

- PBKDF2 password verification; no hardcoded login credentials.
- HttpOnly, SameSite session cookie and a non-HttpOnly CSRF cookie/header pair.
- Origin allowlist and CORS credentials restricted to configured origins.
- API body limit, per-IP route rate limits, strict input validation, and safe error responses.
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and production HSTS headers.
- Corrupt JSON is rejected instead of silently replaced.

These controls are not a substitute for a penetration test, external identity provider, field-level RBAC, tenant isolation, secret manager, or a compliance review.

## Troubleshooting

**Authentication is not configured**

Set `ZOK_ADMIN_EMAIL` and generate `ZOK_ADMIN_PASSWORD_HASH` with the provided script. Restart the API after changing `.env`.

**API returns 401 after idle time**

The session expired or was revoked. Sign in again; do not disable authentication to work around it.

**API returns 403 on a mutation**

The browser must use the same configured origin and the frontend must send the CSRF token from the `zok_csrf` cookie. Check `ZOK_ALLOWED_ORIGINS` and the reverse proxy origin.

**Build or install fails**

```bash
rm -rf node_modules dist
npm ci
npm test
npm run build
```

## Release Status

See `ZOK_COMPLETE_RELEASE_PLAN.md` for the requirement-by-requirement status. Do not market the local adapter as a connected channel platform until the integration, privacy, load, and recovery gates have evidence.
