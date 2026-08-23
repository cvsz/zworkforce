# U.Perfect Historical Planning Export / บันทึกแผนงานเดิม

This file is retained as a redacted historical marker for the original
U.Perfect Social Commerce planning export. It is not executable source and is
not the authority for current behavior.

## ภาษาไทย

เอกสาร export เดิมประกอบด้วยแนวคิด Dashboard, Autobot, Product Memory,
การปิดการขาย, n8n automation, การเชื่อมต่อ Facebook, TikTok Shop, Shopee,
LINE และการรองรับ TH/EN

ค่าตัวอย่างที่เป็น token, key, secret, PIN หรือ passphrase จาก export เดิมถูก
ลบออกทั้งหมดก่อนเก็บใน GitHub เพื่อไม่ให้เอกสารประวัติถูกเข้าใจว่าเป็นค่าใช้งาน
จริงหรือกลายเป็น credential ที่เผยแพร่โดยไม่ตั้งใจ

เอกสารที่ใช้เป็นแหล่งอ้างอิงปัจจุบัน:

- [README](README.md)
- [คู่มือผู้ใช้](USER-MANUAL.md)
- [คู่มือผู้ดูแล](ADMIN-MANUAL.md)
- [คู่มือนักพัฒนา](DEV-MANUAL.md)
- [สารบัญเอกสารโครงการ](PROJECT-DOCUMENTATION.md)
- [เอกสาร API](docs/API.md)
- [เอกสารสถาปัตยกรรม](docs/ARCHITECTURE.md)
- [คู่มือ API ภาษาไทย](docs/integrations/API_ONBOARDING_TH.md)
- [คู่มือ API ภาษาอังกฤษ](docs/integrations/API_ONBOARDING_EN.md)

## English

The original export covered the Dashboard, Autobot, Product Memory, sales
closing, n8n automation, Facebook, TikTok Shop, Shopee, LINE, and TH/EN
support. It was generated as planning material and must not be treated as the
current runtime implementation.

All token, key, secret, PIN, and passphrase-like sample values from the old
export were removed before keeping this marker in GitHub. Provider credentials
belong in the server-side secret system and never in documentation, browser
storage, or source control.

Use the current manuals and project documentation above as the authoritative
contract. The current release is local-only at `192.168.74.130`, keeps provider
connections `unconfigured` until verified, uses a bilingual Dashboard, and
does not create a ZIP archive unless explicitly requested again.
