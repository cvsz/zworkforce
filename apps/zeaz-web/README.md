# ZEAZ Web

Production full-stack website for `https://www.zeaz.dev/` and the ZEAZ One product programme.

## Architecture

- Cloudflare Worker serves the responsive bilingual EN/TH website.
- Cloudflare D1 stores early-access requests and rate-limit audit records.
- `/api/early-access` validates and stores public submissions.
- `/api/admin/early-access` is protected by `ADMIN_API_TOKEN`.
- Optional Resend notification delivery runs asynchronously.
- `/privacy` and `/terms` provide bilingual legal pages.

## API

- `GET /api/health`
- `POST /api/early-access`
- `GET /api/admin/early-access?status=new&limit=50`

## Required production secrets

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `ZEAZ_WEB_ADMIN_API_TOKEN` (minimum 32 characters)
- `ZEAZ_WEB_IP_HASH_SALT` (minimum 32 characters)

Optional: `RESEND_API_KEY`, `ZEAZ_WEB_NOTIFICATION_EMAIL`.

## Advertising activation

- AdSense (`ca-pub-4971034675329740`) loads only when the Worker var
  `GOOGLE_CERTIFIED_CMP_READY` is `"true"`. Default is `"false"`.
- `/ads.txt` serves the publisher authorization line.
- After a Google-certified CMP is installed, set the var durably in
  `apps/zeaz-web/wrangler.template.json` (rendered into the generated
  Wrangler config at deploy time) rather than only via dashboard,
  otherwise the next Wrangler deploy overwrites dashboard-only values.

## Local validation

```bash
pnpm --dir apps/zeaz-web build
pnpm --dir apps/zeaz-web lint
pnpm --dir apps/zeaz-web test
```
