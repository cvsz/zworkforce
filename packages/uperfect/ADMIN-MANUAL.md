# U.Perfect Admin Manual / คู่มือผู้ดูแลระบบและร้านค้า

**Audience:** merchant owner, operations lead, customer-service admin, and reviewer
**Runtime:** LAN-only `192.168.74.130:18765`
**Primary rule:** credentials stay on the server; Dashboard settings are preferences, not an OAuth vault.

## ภาษาไทย

### 1. บทบาทผู้ดูแล

- **Owner:** อนุมัติ provider app/scope, token rotation, production enablement
- **Admin:** ดูแชท รับช่วง ตรวจข้อมูล และสร้าง draft order
- **Reviewer:** ตรวจ payment evidence และยืนยัน order
- **Developer/Operator:** ดู service, logs, tests, adapter, deployment และ release evidence

ไม่ควรให้ผู้ใช้งานทั่วไปมีสิทธิ์อ่าน environment, database file, systemd unit,
GPG key หรือ Cloudflare/Terraform credential

### 2. ตั้งค่าร้านและภาษา

เปิด **Settings** แล้วตรวจ:

- ชื่อร้านและ handle: `U.Perfect`, `@spookyuperfect`
- เขตเวลา: `Asia/Bangkok` ตามค่าเริ่มต้น
- ภาษาเริ่มต้น: TH หรือ EN
- โทน Autobot: warm, formal หรือ concise
- Autobot enabled และ timeout ของ human takeover
- n8n post/comment และ LINE/payment-review notifications

การบันทึก Settings จะเก็บเฉพาะค่าพฤติกรรมและโปรไฟล์ที่อนุญาต ไม่เก็บ token หรือ
secret ใด ๆ

### 3. ตั้งค่า provider แบบถูกลำดับ

1. อ่าน [คู่มือ API ภาษาไทย](docs/integrations/API_ONBOARDING_TH.md) หรือ
   [English API guide](docs/integrations/API_ONBOARDING_EN.md)
2. เปิด [แบบฟอร์มอนุมัติภาษาไทย](docs/integrations/PROVIDER-APPROVAL-FORM_TH.md)
   หรือ [English approval form](docs/integrations/PROVIDER-APPROVAL-FORM_EN.md)
   และกรอกเฉพาะ identifiers/scope/หลักฐานที่ลบ secret แล้ว
3. ให้ account owner ขอสิทธิ์จาก portal ทางการ
4. เก็บค่าที่ได้ใน server environment/secret manager
5. restart service หรือ reload configuration ตาม deployment policy
6. ตรวจ `/api/integrations` และ dashboard Channels
7. ทำ provider ping, webhook test, duplicate event test และ message test
8. เปลี่ยนเป็น production เฉพาะเมื่อมีหลักฐาน `verified`

ห้ามคัดลอก credential ใส่หน้า Settings เพื่อให้สถานะเปลี่ยน เพราะ frontend ไม่ใช่
ที่เก็บ secret และสถานะ `configured` ไม่เท่ากับ `verified`

### 4. จัดการ Product Memory และ Sales Assets

Product Memory คือข้อมูลข้อเท็จจริงจาก merchant brief, catalog และ source listing
ส่วน Sales Assets คือข้อความ TH/EN, intent, CTA และรูป local ที่ตรวจสอบ path แล้ว

ก่อนเปิดใช้สินค้าใหม่:

1. กำหนด stable product ID
2. ระบุชื่อ ขนาด ราคา หรือ `null` หากยังไม่ยืนยัน
3. ระบุ stock, aliases, ingredients, usage, warning และ allergen warning
4. ใส่ promotion เฉพาะที่เจ้าของร้านยืนยัน
5. เพิ่ม local media เข้า asset manifest และตรวจว่า path อยู่ใต้ `assets/`
6. เพิ่ม selling points ทั้ง TH/EN
7. ระบุ `catalog_review` หรือ `admin_review` หากยังขายอัตโนมัติไม่ได้
8. เพิ่ม test สำหรับ keyword, price, objection และ unpriced safety

สินค้าที่ไม่มีราคาห้ามสร้าง order และห้ามใส่เลขราคาจากการคาดเดา

### 5. แนวทางตอบแชทและปิดการขาย

ข้อความที่ดีควร:

- ทักทายและใช้ภาษาเดียวกับลูกค้า
- ยืนยันว่ากำลังคุยสินค้าตัวใด
- ตอบจาก facts ที่มีจริง
- ให้ CTA หนึ่งขั้นตอน เช่น “รับโปร” หรือยืนยันจำนวน
- ถ้าลูกค้าลังเล ให้เสนอข้อมูล/โปรที่ยืนยันแล้วโดยไม่กดดันเกินควร
- ถ้าผิวแพ้ง่าย ให้ patch-test และหยุดใช้เมื่อระคายเคือง ไม่รับรองผล
- ถ้าราคา/สต็อกไม่ยืนยัน ให้ส่งต่อแอดมิน
- ถ้าลูกค้าขอคน ให้เปิด human takeover

ห้าม:

- อ้างว่าเห็นข้อมูลจาก TikTok หาก retrieval ถูก CAPTCHA block
- รับปากว่าส่งฟรีทุกพื้นที่
- รับรองว่าปลอดภัยหรือรักษาโรค
- อนุมัติสลิปด้วย bot เพียงอย่างเดียว
- ส่งข้อความอัตโนมัติหลัง admin takeover

### 6. Payment review และ LINE outbox

ลำดับที่ถูกต้องคือ `awaiting_payment` → `pending_review` → `confirmed` →
`fulfilled` หลังผู้มีสิทธิ์ตรวจสอบหลักฐานแล้วเท่านั้น

เมื่อ order เป็น `confirmed` ระบบจะสร้าง LINE outbox event หาก sender พร้อม
ผู้ดูแลต้องตรวจ pending/failed events และให้ `uperfect-worker.service` ส่งที่
server-side ไม่ส่ง token ผ่าน browser

ตรวจ worker และ migration ได้ด้วย:

```bash
systemctl --user status uperfect-worker.service
systemctl --user restart uperfect-worker.service
.venv/bin/python -m pytest -q tests/test_worker.py tests/test_migrations.py
```

ถ้าไม่มี `LINE_CHANNEL_ACCESS_TOKEN` หรือ `LINE_ADMIN_DESTINATION` worker จะ
หยุดส่งอย่างตั้งใจและคง event ไว้ใน outbox ไม่ใช่รายงานว่าส่งสำเร็จ

### 6.1 Webhook security

normalized webhook ต้องมี HMAC ตาม provider และ secret อยู่ใน server environment:

| Provider | Header | Environment |
| --- | --- | --- |
| Facebook | `X-Hub-Signature-256: sha256=<hex>` | `FACEBOOK_APP_SECRET` |
| LINE | `X-Line-Signature: <base64>` | `LINE_CHANNEL_SECRET` |
| TikTok/Shopee normalized boundary | `X-UPerfect-Webhook-Signature: sha256=<hex>` | `TIKTOK_WEBHOOK_SECRET` / `SHOPEE_WEBHOOK_SECRET` |

ห้ามใช้ `X-UPerfect-Webhook-Verified: true` อีกต่อไป และห้ามส่ง raw provider
payload เข้า normalized route ก่อน adapter ตรวจ signature/state ของ provider

### 7. n8n และ Auto Update

เมนู n8n มีไว้แสดง workflow intent และสถานะ gate:

- Scheduled post
- Comment reply
- Social Auto Update

ห้ามเปิด switch เป็นหลักฐานว่า workflow ยิงออกจริง ต้องมี n8n webhook, account
verification, idempotency, retry policy และ test log ก่อน

### 8. ตรวจสุขภาพระบบ

```bash
curl http://192.168.74.130:18765/api/health
curl http://192.168.74.130:18765/api/integrations
curl http://192.168.74.130:18765/api/notifications
systemctl --user status uperfect.service
```

ตรวจ local AI ได้จาก Settings หรือ `GET /api/integrations`; ต้องพบ
`zCoder:latest` ที่ `192.168.74.130:11434` จึงถือว่า local AI configured

## English

### 1. Admin roles

- **Owner:** approves provider apps/scopes, token rotation, and production enablement
- **Admin:** handles chats, takeover, catalog review, and draft orders
- **Reviewer:** checks payment evidence and confirms orders
- **Developer/Operator:** owns services, logs, tests, adapters, deployment, and release evidence

Do not grant ordinary users access to environment files, the database, systemd
units, GPG keys, or Cloudflare/Terraform credentials.

### 2. Store and language settings

Open **Settings** and review:

- store name and handle: `U.Perfect`, `@spookyuperfect`
- timezone: `Asia/Bangkok` by default
- default TH/EN language
- Autobot tone: warm, formal, or concise
- Autobot enablement and human takeover timeout
- n8n post/comment and LINE/payment-review preferences

Settings stores only allowed profile and behavior values. It never stores tokens
or secrets.

### 3. Configure providers in order

1. Read the [Thai API guide](docs/integrations/API_ONBOARDING_TH.md) or the
   [English API guide](docs/integrations/API_ONBOARDING_EN.md).
2. Open the [Thai approval form](docs/integrations/PROVIDER-APPROVAL-FORM_TH.md)
   or [English approval form](docs/integrations/PROVIDER-APPROVAL-FORM_EN.md)
   and record only identifiers, scopes, and redacted evidence.
3. Have the account owner request access through the official portal.
4. Store returned values in the server environment or a secret manager.
5. Restart or reload the service according to deployment policy.
6. Check `/api/integrations` and the Dashboard Channels view.
7. Run provider ping, webhook, duplicate-event, and message tests.
8. Enable production only with `verified` evidence.

Do not paste credentials into Settings. The frontend is not a secret vault, and
`configured` is not the same as `verified`.

### 4. Product Memory and Sales Assets

Product Memory holds merchant facts, catalog data, and source listings. Sales
Assets holds TH/EN copy, intents, CTAs, and validated local media.

Before enabling a new product:

1. Assign a stable product ID.
2. Set name, size, price, or `null` when unverified.
3. Set stock, aliases, ingredients, usage, warning, and allergen warning.
4. Add only owner-confirmed promotions.
5. Add local media to the manifest and keep paths under `assets/`.
6. Add selling points in both TH and EN.
7. Mark `catalog_review` or `admin_review` when automation is not allowed.
8. Add tests for keywords, price, objections, and unpriced safety.

An unpriced product must not produce an order or an invented total.

### 5. Chat and closing policy

The reply should:

- greet the customer and follow their language
- identify the active product
- answer from verified facts
- use one clear next-step CTA
- handle hesitation with confirmed information without pressure
- recommend a patch test for sensitive skin and never promise a medical outcome
- escalate when price or stock is unverified
- pause automation when the customer asks for a person

Never claim TikTok media was exported when retrieval was CAPTCHA-blocked, promise
universal free shipping, guarantee safety or medical results, approve a payment
slip automatically, or reply after human takeover.

### 6. Payment review and LINE outbox

The guarded lifecycle is `awaiting_payment` -> `pending_review` -> `confirmed` ->
`fulfilled`, with authorized review required before confirmation.

Confirmed orders create a LINE outbox event. The separate
`uperfect-worker.service` claims it with a lease, delivers it when the server
has both LINE values, and leaves it retryable on failure. Never send a token
through the browser.

```bash
systemctl --user status uperfect-worker.service
systemctl --user restart uperfect-worker.service
.venv/bin/python -m pytest -q tests/test_worker.py tests/test_migrations.py
```

With no `LINE_CHANNEL_ACCESS_TOKEN` or `LINE_ADMIN_DESTINATION`, the worker is
intentionally dormant and keeps events in the outbox.

### 6.1 Webhook security

The normalized webhook boundary requires HMAC over the exact raw request body:

| Provider | Header | Environment |
| --- | --- | --- |
| Facebook | `X-Hub-Signature-256: sha256=<hex>` | `FACEBOOK_APP_SECRET` |
| LINE | `X-Line-Signature: <base64>` | `LINE_CHANNEL_SECRET` |
| TikTok/Shopee normalized boundary | `X-UPerfect-Webhook-Signature: sha256=<hex>` | `TIKTOK_WEBHOOK_SECRET` / `SHOPEE_WEBHOOK_SECRET` |

`X-UPerfect-Webhook-Verified: true` is no longer accepted. Raw provider payloads
must pass provider-specific signature/state validation in an adapter first.

### 7. n8n and Auto Update

The n8n view describes scheduled posts, comment replies, and social Auto Update.
These are not live just because a preference is enabled. Require a verified
webhook, account approval, idempotency, retry policy, and test log first.

### 8. Health checks

```bash
curl http://192.168.74.130:18765/api/health
curl http://192.168.74.130:18765/api/integrations
curl http://192.168.74.130:18765/api/notifications
systemctl --user status uperfect.service
systemctl --user status uperfect-worker.service
```

The local AI status is configured only when `zCoder:latest` is visible from
`192.168.74.130:11434`.
