# U.Perfect Security Policy / นโยบายความปลอดภัย

## ภาษาไทย

### ข้อมูลลับ

ถือว่าเป็นความลับเสมอ:

- provider access/refresh token, app secret, partner key, channel secret
- webhook verification token และ signing material
- database credential, Cloudflare/Terraform credential
- GPG private key, PIN และ passphrase

ห้ามใส่ข้อมูลเหล่านี้ใน source, PWA, asset JSON, SQL seed, log, screenshot,
issue, PR หรือคู่มือ

### ขอบเขตความเสี่ยง

- Browser เรียกเฉพาะ API ที่ไม่ส่ง secret กลับ
- raw provider webhook ต้องผ่าน signature/state validation ก่อน normalize
- event ต้องมี idempotency เพื่อป้องกันข้อความ/ออเดอร์ซ้ำ
- payment evidence ไม่ใช่ payment approval
- human takeover ต้องหยุด bot สำหรับบทสนทนานั้น
- local-only AI จำกัดที่ `192.168.74.130`

### การแจ้งช่องโหว่

อย่าเปิด issue สาธารณะพร้อมรายละเอียดที่ใช้โจมตีได้ ให้ส่งให้ owner ผ่านช่องทาง
ส่วนตัวพร้อม version, reproduction ที่ไม่มี secret, impact และ mitigation ที่ลองแล้ว

### Secret handling

เก็บ secret ในระบบ server/secret manager ที่จำกัดสิทธิ์ หมุนและ revoke เมื่อสงสัย
ว่ารั่ว ตรวจ `git diff` และ release artifact ทุกครั้งก่อน push

## English

Always treat provider access/refresh tokens, app secrets, partner keys, channel
secrets, webhook signing material, database credentials, Cloudflare/Terraform
credentials, GPG private keys, PINs, and passphrases as secret.

Never place them in source, the PWA, asset JSON, SQL seeds, logs, screenshots,
issues, pull requests, or manuals. The browser receives only secret-free API
payloads. Raw provider webhooks must pass signature/state validation before
normalization, events must be idempotent, payment evidence is not approval, human
takeover pauses automation, and local AI is restricted to `192.168.74.130`.

Report suspected vulnerabilities privately to the project owner with version,
secret-free reproduction, impact, and attempted mitigation. Store secrets in a
server-side secret manager, rotate/revoke on suspicion, and inspect diffs and
release artifacts before pushing.
