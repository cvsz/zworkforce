# U.Perfect Deployment / การ deploy U.Perfect

## ภาษาไทย

### ขอบเขต release ปัจจุบัน

Runtime หลักเป็น FastAPI + PWA แบบ local-only ที่ bind อยู่กับ
`192.168.74.130:18765` และใช้ Ollama ที่ `192.168.74.130:11434` สำหรับ
`zCoder:latest` เท่านั้นเมื่อ model พร้อมใช้งาน

```bash
systemctl --user daemon-reload
systemctl --user enable --now uperfect.service uperfect-worker.service
systemctl --user status uperfect.service
systemctl --user status uperfect-worker.service
curl -fsS http://192.168.74.130:18765/api/health
```

ไฟล์ unit อยู่ที่ `deploy/systemd/uperfect.service` และ
`deploy/systemd/uperfect-worker.service`; ต้องตรวจ owner/process ก่อน restart
ทุกครั้ง

worker ใช้ database เดียวกับ API, claim notification ด้วย lease และ retry
failure แบบ bounded backoff. ถ้าไม่มี `LINE_CHANNEL_ACCESS_TOKEN` หรือ
`LINE_ADMIN_DESTINATION` จะไม่ทำ network call และคง event ไว้ใน outbox

แม่แบบเพิ่มเติมอยู่ที่ `deploy/README.md`, `deploy/Dockerfile`,
`deploy/docker-compose.yml` และ `deploy/nginx/uperfect.conf.example` โดย Compose
และ Nginx เป็นทางเลือก ไม่ได้เปลี่ยน owner ของ runtime ที่ใช้อยู่ และต้องตรวจ
พอร์ต `192.168.74.130:18765` ก่อนใช้

การขอสิทธิ์ Facebook/Meta, TikTok Shop, Shopee และ LINE ให้ใช้คู่มือใน
`docs/integrations/API_ONBOARDING_TH.md` หรือ `_EN.md` และกรอกแบบฟอร์ม
`PROVIDER-APPROVAL-FORM_TH.md`/`_EN.md` โดยไม่ใส่ secret ค่าที่ provider ใช้เป็น
callback/webhook ห้ามชี้ตรงไปที่ `192.168.74.130`; ต้องเป็น public HTTPS adapter
ที่ตรวจ signature/state ฝั่ง server ก่อนส่ง event เข้า local service

### Public route

`uperfect.zeaz.dev` เป็น public route ที่จัดการนอก repository นี้ โดย
Cloudflare/Terraform ใช้ origin ภายใน `http://192.168.74.130:18765` ตาม
deployment environment ของ owner โปรเจกต์ Terraform ที่เป็น owner ของ route อยู่
ที่ `/home/cvsz/zeaz/infrastructure/terraform/cloudflare/` บนเครื่อง deployment
ไม่ใช่ source directory ของแอปนี้

ตรวจ local และ public แยกกัน:

```bash
curl -fsS http://192.168.74.130:18765/api/health
curl -fsS https://uperfect.zeaz.dev/api/health
```

Local `200` ไม่ใช่หลักฐานว่า Cloudflare tunnel, DNS, TLS หรือ public route ใช้งาน
ได้ ต้องตรวจ response จาก public URL หลัง apply ทุกครั้ง

### Secret และ rollback

ห้ามใส่ Cloudflare API token, Terraform state, tunnel credential หรือ provider
secret ใน repository, PWA, log หรือ screenshot ใช้ secret backend/environment ของ
deployment เท่านั้น ก่อน apply ให้รัน `terraform plan` และเก็บ plan/evidence ที่
ไม่มี secret หาก route ผิดให้หยุด public exposure, ตรวจ origin/ingress และ rollback
ผ่าน owner ของ Terraform โดยไม่แก้ application database เป็นทางลัด

ZIP export ถูกยกเลิกและไม่สร้าง archive ใน release นี้

## English

### Current release boundary

The application is a local-only FastAPI + PWA runtime bound to
`192.168.74.130:18765`. The no-cost AI boundary is Ollama at
`192.168.74.130:11434`, using `zCoder:latest` only when that model is available.

```bash
systemctl --user daemon-reload
systemctl --user enable --now uperfect.service uperfect-worker.service
systemctl --user status uperfect.service
systemctl --user status uperfect-worker.service
curl -fsS http://192.168.74.130:18765/api/health
```

The units are `deploy/systemd/uperfect.service` and
`deploy/systemd/uperfect-worker.service`. Identify the owning unit and process
before restarting anything. The worker shares the database, claims notifications
with a lease, and retries with bounded backoff. Without both
`LINE_CHANNEL_ACCESS_TOKEN` and `LINE_ADMIN_DESTINATION`, it makes no network
call and leaves events in the outbox.

Additional templates are in `deploy/README.md`, `deploy/Dockerfile`,
`deploy/docker-compose.yml`, and `deploy/nginx/uperfect.conf.example`. Compose
and Nginx are optional and do not replace the current systemd owner; verify that
`192.168.74.130:18765` is available before using them.

Use `docs/integrations/API_ONBOARDING_EN.md` and
`docs/integrations/PROVIDER-APPROVAL-FORM_EN.md` for provider access and owner
evidence. Provider callbacks/webhooks must not point directly to
`192.168.74.130`; use a public HTTPS adapter with server-side signature/state
validation before forwarding events to the local service. The normalized local
route also requires provider-specific HMAC over the exact raw body; it is not a
replacement for the public adapter.

### Public route

`uperfect.zeaz.dev` is managed outside this repository. The Cloudflare/Terraform
deployment uses the internal origin `http://192.168.74.130:18765` in the owner’s
deployment environment. The Terraform owner directory is
`/home/cvsz/zeaz/infrastructure/terraform/cloudflare/` on the deployment host;
it is not this application source directory.

Verify local and public routes separately:

```bash
curl -fsS http://192.168.74.130:18765/api/health
curl -fsS https://uperfect.zeaz.dev/api/health
```

A local `200` does not prove that the Cloudflare tunnel, DNS, TLS, or public route
works. Check the public response after every infrastructure apply.

### Secrets and rollback

Never commit Cloudflare API tokens, Terraform state, tunnel credentials, or
provider secrets to this repository, the PWA, logs, or screenshots. Use the
deployment environment/secret backend. Run `terraform plan` before applying and
retain only redacted evidence. If routing is wrong, stop public exposure, trace
origin/ingress ownership, and roll back through the Terraform owner instead of
editing application data as a shortcut.

ZIP export is canceled and no archive is generated in this release.
