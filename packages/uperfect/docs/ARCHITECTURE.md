# U.Perfect Architecture / สถาปัตยกรรมระบบ

## ภาษาไทย

ระบบแบ่งเป็นชั้นที่ชัดเจน:

```text
PWA Dashboard (TH/EN)
        |
FastAPI JSON transport
        |
Domain services
  | catalog | conversations | sales assets | orders | integrations | outbox
        |
SQLite local store + schema migrations + local files
        |
LAN host 192.168.74.130

Confirmed order -> notification_outbox -> leased worker -> LINE push transport
                         ^
                   retry/backoff
```

- `web/` แสดงผลและเรียก API โดยไม่เก็บ secret
- `app/api.py` เป็น transport และ schema ของ request
- `app/services/` บังคับ business rule, safety, idempotency และ review gate
- `app/repositories.py` เป็น transaction boundary ของ SQLite
- `assets/chatbot/` เป็น source of truth ของ response assets TH/EN
- provider adapter ที่ production ต้องอยู่ server-side ก่อน normalized webhook
- normalized webhook ตรวจ HMAC จาก raw body; LINE เป็น retryable outbox และมี
  signed normalized intake boundary แต่ยังไม่ใช่ live inbound chatbot adapter
- `app/migrations.py` บันทึก `schema_migrations` และ apply additive changes โดย
  ไม่ใช้ Alembic/Redis/บริการเสียเงิน

ลำดับปิดการขายคือ `keyword/context -> intent -> catalog fact -> CTA -> draft
order -> payment review -> authorized confirmation` ระบบไม่ข้ามขั้นตอน review

## English

The system has explicit boundaries:

- `web/` renders the PWA and calls APIs without receiving secrets.
- `app/api.py` owns transport and request validation.
- `app/services/` owns business rules, safety, idempotency, and review gates.
- `app/repositories.py` is the SQLite transaction boundary.
- `assets/chatbot/` is the TH/EN response-asset source of truth.
- Production provider adapters must validate raw events server-side before normalization.
- The normalized boundary verifies HMAC over raw bytes; raw provider adapters still
  own provider-specific validation.
- LINE is a retryable outbox delivered by `app/worker.py` in this release, not a
  live inbound chatbot channel.
- `app/migrations.py` records additive schema versions without Alembic, Redis, or
  paid infrastructure.

The closing path is `keyword/context -> intent -> catalog fact -> CTA -> draft
order -> payment review -> authorized confirmation`. The system never skips review.

## Trust boundaries / ขอบเขตความเชื่อถือ

1. Customer/provider payloads are untrusted.
2. Provider signatures and authorization state must be checked server-side.
3. Browser settings are non-secret preferences.
4. Order confirmation requires an authorized reviewer.
5. GPG, Cloudflare, marketplace, and LINE credentials are deployment secrets.
