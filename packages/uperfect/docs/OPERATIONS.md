# U.Perfect Operations Runbook / คู่มือปฏิบัติการ

## ภาษาไทย

### Start/stop/status

```bash
systemctl --user status uperfect.service
systemctl --user restart uperfect.service
curl -fsS http://192.168.74.130:18765/api/health
```

ตรวจว่า process bind ที่ `192.168.74.130:18765` ไม่ใช่เพียง loopback อื่น และ
อย่า restart service ชื่อคล้ายกันโดยไม่ตรวจ unit ก่อน

### Local AI

Runtime ต้องใช้ `http://192.168.74.130:11434` และ `zCoder:latest` เท่านั้นใน
local-only profile ตรวจด้วย:

```bash
curl -fsS http://192.168.74.130:11434/api/tags
curl -fsS http://192.168.74.130:18765/api/integrations
```

### Incident response

1. บันทึกเวลา URL และอาการ โดยไม่แนบ credential
2. แยก local API, LAN route, public route, provider API และ outbox
3. ตรวจ logs และ `/api/health`
4. ปิด Autobot หรือเปิด human takeover หากมีการตอบผิด
5. ห้ามแก้ราคา/สต็อก/สถานะ order ด้วยมือใน database โดยไม่ audit
6. เก็บหลักฐานก่อน restart หรือ rollback
7. หากเป็น provider ให้ตรวจ approval workbook, callback ownership และสถานะ
   `configured`/`verified` แยกกันก่อนเปิดใช้

### Backup/restore

สำรอง `uperfect.db` ด้วยการหยุด mutation หรือใช้ snapshot ที่สอดคล้องกัน เก็บ
ไฟล์นอก web root และทดสอบ restore เป็นระยะ ห้ามสำรอง `.env` หรือ credential
พร้อม database โดยไม่เข้ารหัสและจำกัดสิทธิ์

## English

### Start/stop/status

```bash
systemctl --user status uperfect.service
systemctl --user restart uperfect.service
curl -fsS http://192.168.74.130:18765/api/health
```

Confirm the process binds to `192.168.74.130:18765`, not only another loopback
address. Do not restart a similarly named service without checking the unit.

### Local AI

The local-only profile is restricted to `http://192.168.74.130:11434` and
`zCoder:latest`. Check `/api/tags` and `/api/integrations`.

### Incident response

Record time, URL, and symptoms without credentials. Separate local API, LAN
route, public route, provider API, and notification outbox. Check health/logs,
pause automation or enable takeover when replies are unsafe, and preserve
evidence before restart or rollback. For provider incidents, review the approval
workbook and keep `configured` separate from `verified`.

### Backup/restore

Back up `uperfect.db` from a consistent point, store it outside the web root,
and test restoration. Do not bundle `.env` or credentials with an unencrypted
database backup.
