# Contributing to U.Perfect / แนวทางร่วมพัฒนา

## ภาษาไทย

### ก่อนเริ่ม

อ่าน [DEV-MANUAL.md](DEV-MANUAL.md), [SECURITY.md](SECURITY.md) และเอกสารที่
เกี่ยวข้องกับงานก่อนแก้โค้ด หากงานแตะ provider, payment, Cloudflare, Terraform,
GPG หรือ credential ให้ระบุ owner และ verification evidence ให้ชัด

### Workflow

1. สร้าง branch ที่อธิบายงาน
2. แก้เฉพาะไฟล์ใน scope และรักษา unrelated changes
3. เพิ่ม/แก้ test ก่อนหรือพร้อม implementation
4. หากแก้ UI ให้ตรวจ TH และ EN บน mobile/desktop
5. หากแก้ asset ให้รัน loader validation และตรวจ no external media
6. รัน test, compile, JS syntax check และ `git diff --check`
7. เปิด PR ด้วย template และระบุสิ่งที่ยังเป็น deployment gate

### Secret และ signed commit

ห้าม commit `.env`, database secret, access/refresh token, partner key, channel
secret, GPG PIN หรือ passphrase ใช้ GPG agent ที่ตั้งค่าไว้สำหรับ signed commit
เท่านั้น หาก agent ไม่พร้อม ให้หยุดและแจ้ง ไม่ใช้ `--pinentry-mode loopback` พร้อม
PIN ใน command

### Definition of done

งานเสร็จเมื่อ code, tests, docs, bilingual UI และ runtime evidence สอดคล้องกัน
และไม่มีการอ้าง provider live โดยไม่มีหลักฐาน

## English

Read [DEV-MANUAL.md](DEV-MANUAL.md), [SECURITY.md](SECURITY.md), and the relevant
provider documentation before editing. Provider, payment, Cloudflare, Terraform,
GPG, and credential work must name an owner and verification evidence.

1. Create a scoped branch.
2. Preserve unrelated changes.
3. Add or update tests with the implementation.
4. Check TH and EN on mobile and desktop for UI changes.
5. Validate the asset loader and local-media policy for asset changes.
6. Run tests, compile checks, JS syntax, and `git diff --check`.
7. Use the PR template and document remaining deployment gates.

Never commit `.env`, database secrets, access/refresh tokens, partner keys,
channel secrets, GPG PINs, or passphrases. Use the configured GPG agent for
signed commits; never put a passphrase in a command. Done means code, tests,
docs, bilingual UI, and runtime evidence agree without overstating provider state.
