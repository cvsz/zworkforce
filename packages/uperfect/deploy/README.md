# U.Perfect Deployment Templates / แม่แบบ Deployment

## ภาษาไทย

Release นี้รองรับ runtime แบบ local-only ที่ `192.168.74.130:18765` และใช้
Ollama ที่ `192.168.74.130:11434` กับ `zCoder:latest` เท่านั้น

- `systemd/uperfect.service`: API unit ที่ใช้อยู่กับ `/mnt/uperfect/.venv`
- `systemd/uperfect-worker.service`: notification outbox worker unit ที่ใช้
  database เดียวกับ API
- `Dockerfile`: image แบบ Python 3.12 ที่รันด้วย user `uperfect` ที่ไม่ใช่ root
- `docker-compose.yml`: Compose ตัวอย่างพร้อม named volume สำหรับ SQLite และ
  bind port ที่ `192.168.74.130:18765`
- `nginx/uperfect.conf.example`: reverse proxy template สำหรับ
  `uperfect.zeaz.dev`; certificate และ DNS เป็นความรับผิดชอบของ deployment owner

### Systemd

```bash
systemctl --user daemon-reload
systemctl --user enable --now uperfect.service uperfect-worker.service
systemctl --user status uperfect-worker.service
curl -fsS http://192.168.74.130:18765/api/health
```

### Docker Compose (ทางเลือก)

รันจาก root ของ repository และตรวจว่าพอร์ตเดิมไม่มี service อื่นใช้งานอยู่:

```bash
docker compose -f deploy/docker-compose.yml config
docker compose -f deploy/docker-compose.yml up -d --build
curl -fsS http://192.168.74.130:18765/api/health
```

อย่าใส่ `.env`, provider token, Cloudflare credential หรือ Terraform state ใน
image/Compose file. ก่อนใช้จริงต้องมี backup ของ `uperfect.db`, ตรวจ owner ของ
origin และบันทึก rollback command. Worker จะไม่ส่ง network call จนกว่าจะมีทั้ง
`LINE_CHANNEL_ACCESS_TOKEN` และ `LINE_ADMIN_DESTINATION` ใน environment ฝั่ง
server

## English

This release supports a local-only runtime at `192.168.74.130:18765` and the
no-cost Ollama boundary at `192.168.74.130:11434` with `zCoder:latest` only.

- `systemd/uperfect.service`: the current API unit using `/mnt/uperfect/.venv`
- `systemd/uperfect-worker.service`: the notification outbox worker sharing the
  API database
- `Dockerfile`: Python 3.12 image running as the non-root `uperfect` user
- `docker-compose.yml`: example Compose deployment with a named SQLite volume
  and the documented LAN bind
- `nginx/uperfect.conf.example`: optional reverse proxy template for
  `uperfect.zeaz.dev`; DNS and certificates belong to the deployment owner

### Systemd

```bash
systemctl --user daemon-reload
systemctl --user enable --now uperfect.service uperfect-worker.service
systemctl --user status uperfect-worker.service
curl -fsS http://192.168.74.130:18765/api/health
```

### Docker Compose (optional)

Run from the repository root after confirming the port is owned by this
deployment:

```bash
docker compose -f deploy/docker-compose.yml config
docker compose -f deploy/docker-compose.yml up -d --build
curl -fsS http://192.168.74.130:18765/api/health
```

Never put `.env`, provider tokens, Cloudflare credentials, or Terraform state in
the image or Compose file. Back up `uperfect.db`, verify origin ownership, and
record a rollback command before production use. The worker makes no network
call until both `LINE_CHANNEL_ACCESS_TOKEN` and `LINE_ADMIN_DESTINATION` exist
in the server environment.
