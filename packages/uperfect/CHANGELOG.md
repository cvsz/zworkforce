# Changelog / ประวัติการเปลี่ยนแปลง

## 2026-08-10 - v1.0.0-local-final

### Added / เพิ่ม

- additive SQLite schema migration metadata and PostgreSQL outbox parity migration
- leased notification outbox delivery worker with bounded retry/backoff and
  server-only LINE push transport
- provider-specific HMAC verification over raw normalized webhook bodies for
  Facebook, LINE, TikTok, and Shopee boundaries
- API-path E2E order/outbox tests, frontend API/i18n contract tests, and worker
  deployment units for systemd and Compose
- validated bilingual TH/EN sales response asset pack
- local product asset manifest and `/api/sales-assets`
- bilingual provider onboarding for Facebook, TikTok Shop, Shopee, and LINE
- `/api/integration-guides` and Dashboard guide links
- bilingual provider approval workbooks for Facebook/Meta, TikTok Shop, Shopee,
  and LINE with secret-free owner sign-off fields
- Dashboard `Sales Assets` view with local media and closing CTAs
- Dashboard-wide TH/EN rendering for navigation, status, forms, and operational views
- `USER-MANUAL.md`, `ADMIN-MANUAL.md`, `DEV-MANUAL.md`, project docs, and GitHub templates
- canonical ASCII product asset directories, bilingual soap references, and
  manifest path tests
- GitHub Actions CI plus non-root Docker, local-only Compose, and Nginx templates
- LINE Developers July 2026 compatibility note in the TH/EN onboarding guides

### Safety / ความปลอดภัย

- unpriced products remain admin review and cannot create orders
- payment confirmation remains an authorized review action
- human takeover pauses automated replies
- provider credentials remain server-side
- webhook signatures are verified server-side; the removed boolean test header
  is not accepted
- ZIP export is canceled; no archive is generated or published

### Not claimed / สิ่งที่ยังไม่อ้างว่าเสร็จ

- live Facebook, TikTok Shop, Shopee, LINE inbound, n8n, or Gemini delivery
- live raw provider adapters and provider portal verification
- payment slip verification by an external service
- TikTok public media export when CAPTCHA blocks access
