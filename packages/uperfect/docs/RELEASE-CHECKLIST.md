# U.Perfect Release Checklist / เช็กลิสต์ก่อน release

## ภาษาไทย

### Code and tests

- [ ] `.venv/bin/python -m pytest -q`
- [ ] `.venv/bin/python -m compileall -q app scripts tests`
- [ ] `.venv/bin/python -m pytest -q tests/test_migrations.py tests/test_worker.py tests/test_e2e.py`
- [ ] `node --check web/app.js`
- [ ] `git diff --check`
- [ ] `tests/test_ci_and_deploy.py` ผ่าน และ `docker compose -f deploy/docker-compose.yml config` ผ่านถ้ามี Docker
- [ ] ตรวจ no secret/token/PIN/passphrase ใน diff และ artifact

### Dashboard

- [ ] เปิดทุก view ได้บน desktop และ mobile
- [ ] TH/EN เปลี่ยน navigation, title, status, forms, Sales Assets และ API guides
- [ ] Channels และ Settings เปิดลิงก์คู่มือ/แบบฟอร์มอนุมัติ TH/EN ได้ครบ
- [ ] รูป local โหลดได้และไม่มี external media ที่ไม่ได้อนุมัติ
- [ ] service worker version ถูก bump หลัง shell change

### Business safety

- [ ] ราคาและ promotion ผูกกับ catalog
- [ ] สินค้าไม่มีราคาสร้าง order ไม่ได้
- [ ] sensitive skin มี patch-test
- [ ] human takeover หยุด automated reply
- [ ] payment evidence ต้องผ่าน `pending_review`
- [ ] confirmed order เท่านั้นที่สร้าง LINE outbox event
- [ ] worker claim lease/backoff และ dormant no-credential path ผ่าน

### Provider and deployment

- [ ] account owner อนุมัติ scope
- [ ] กรอก [Provider Approval Form](integrations/PROVIDER-APPROVAL-FORM_TH.md) โดยไม่มี secret
- [ ] webhook signature/state validation อยู่ server-side
- [ ] normalized webhook ใช้ HMAC จาก raw body; ไม่มี `X-UPerfect-Webhook-Verified` bypass
- [ ] `uperfect-worker.service` และ Compose `worker` ใช้ database เดียวกับ API
- [ ] external callback ไม่ชี้ไปที่ private LAN IP และมี public HTTPS adapter
- [ ] provider duplicate/rate-limit/retry test ผ่าน
- [ ] local AI ตรวจ `192.168.74.130:11434` และ model ที่ระบุ
- [ ] public route และ LAN route ตรวจแยกกัน
- [ ] ZIP export ยังคง canceled หากไม่มีคำขอใหม่

## English

### Code and tests

- [ ] Run pytest, compileall, `node --check`, and `git diff --check`.
- [ ] Run migration, worker, and API-path E2E tests.
- [ ] Run the CI/deployment contract tests and validate Compose config when Docker is available.
- [ ] Search the diff and artifacts for secrets, tokens, PINs, and passphrases.

### Dashboard

- [ ] Every view works on desktop and mobile.
- [ ] TH/EN changes navigation, title, status, forms, Sales Assets, and guide links.
- [ ] Channels and Settings expose the TH/EN setup guides and approval workbooks.
- [ ] Local images load without unapproved external media.
- [ ] Service-worker shell version is bumped after shell changes.

### Business safety

- [ ] Prices and promotions are catalog-bound.
- [ ] Unpriced products cannot create orders.
- [ ] Sensitive-skin copy includes patch-test guidance.
- [ ] Human takeover pauses automated replies.
- [ ] Payment evidence stays in `pending_review`.
- [ ] Only confirmed orders create LINE outbox events.
- [ ] Worker lease/backoff and no-credential dormant behavior are tested.

### Provider and deployment

- [ ] The account owner approved scopes.
- [ ] Complete the [Provider Approval Form](integrations/PROVIDER-APPROVAL-FORM_EN.md) without secrets.
- [ ] Signature/state validation runs server-side.
- [ ] Normalized webhooks use HMAC over raw bytes; the boolean bypass is absent.
- [ ] The systemd worker and Compose worker share the API database.
- [ ] External callbacks use a public HTTPS adapter, never a private LAN IP.
- [ ] Duplicate, rate-limit, and retry tests have evidence.
- [ ] Local AI is checked at `192.168.74.130:11434`.
- [ ] LAN and public routes are verified separately.
- [ ] ZIP export remains canceled unless explicitly requested again.
