# U.Perfect API Integration Guides / คู่มือเชื่อมต่อ API

This directory contains the account-owner onboarding guide for Facebook
Messenger, TikTok Shop, Shopee, and LINE Messaging API.

โฟลเดอร์นี้เป็นคู่มือสำหรับเจ้าของบัญชีในการขอสิทธิ์ API ของ Facebook
Messenger, TikTok Shop, Shopee และ LINE Messaging API

## Choose a language / เลือกภาษา

- [ภาษาไทย](API_ONBOARDING_TH.md)
- [English](API_ONBOARDING_EN.md)
- [แบบฟอร์มอนุมัติภาษาไทย](PROVIDER-APPROVAL-FORM_TH.md)
- [English approval form](PROVIDER-APPROVAL-FORM_EN.md)

## Current release boundary / ขอบเขตของ release ปัจจุบัน

The dashboard can show provider status, guide links, and secret-free setup
fields. It does not perform OAuth, token exchange, payment verification, or
provider-specific webhook signature validation in the browser. The server
validates HMAC over the exact raw body at the normalized boundary.

Dashboard สามารถแสดงสถานะ provider ลิงก์คู่มือ และช่องกรอกค่าตั้งค่าแบบไม่เปิดเผย
secret ได้ แต่ยังไม่ทำ OAuth, token exchange, payment verification หรือการตรวจ
ลายเซ็น webhook เฉพาะ provider ใน browser; server จะตรวจ HMAC จาก raw body ที่
normalized boundary

เจ้าของบัญชีใช้แบบฟอร์มอนุมัติเพื่อเก็บ identifiers, scopes, callback/webhook,
review evidence และ sign-off โดยไม่เก็บ credential

All provider statuses remain `unconfigured` until the account owner completes
the official portal setup and the server-side verification gate. LINE is an
outbound notification outbox in this release; inbound LINE chatbot delivery is
not enabled.

สถานะ provider จะเป็น `unconfigured` จนกว่าเจ้าของบัญชีจะตั้งค่าจาก portal
ทางการและผ่าน server-side verification โดย release นี้ LINE ใช้เป็น outbound
notification outbox เท่านั้น ยังไม่เปิดรับแชท LINE ขาเข้า

## Local test endpoints

- Dashboard: `http://192.168.74.130:18765/`
- Health: `GET /api/health`
- Normalized message test: `POST /api/messages`
- Normalized webhook test: `POST /api/webhooks/{provider}`
- Sales assets: `GET /api/sales-assets`
- This guide index: `GET /api/integration-guides`

The normalized local webhook test requires a provider-specific HMAC over the
exact raw body. Use `X-Hub-Signature-256` for Facebook,
`X-Line-Signature` for LINE, and `X-UPerfect-Webhook-Signature` for the
normalized TikTok/Shopee boundary. Provider raw payloads must not be sent to
this route until an official provider adapter performs provider-specific
signature/state validation and normalizes the event.

การทดสอบ webhook ภายในต้องส่ง HMAC จาก raw body ตาม provider: Facebook ใช้
`X-Hub-Signature-256`, LINE ใช้ `X-Line-Signature` และ normalized TikTok/Shopee
ใช้ `X-UPerfect-Webhook-Signature` ห้ามส่ง raw payload ของ provider เข้า route
นี้จนกว่าจะมี adapter ที่ตรวจ signature/state ของ provider และแปลง event เป็น
รูปแบบกลางเรียบร้อยแล้ว

External provider callbacks cannot target `192.168.74.130` directly. A public
HTTPS adapter and server-side signature validation are required before live
provider traffic is enabled.
