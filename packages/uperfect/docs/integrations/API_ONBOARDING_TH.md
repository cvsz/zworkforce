# คู่มือขอ API และตั้งค่าเชื่อมต่อ U.Perfect

**ระบบ:** U.Perfect Social Commerce OS
**โหมดปัจจุบัน:** Local-only ที่ `192.168.74.130`
**สถานะเริ่มต้นของ provider:** `unconfigured`
**เจ้าของการอนุมัติ:** เจ้าของบัญชีธุรกิจของแต่ละแพลตฟอร์ม

เอกสารนี้เป็นคู่มือปฏิบัติสำหรับขอสิทธิ์ API จาก portal ทางการ แล้วนำค่าที่ได้
ไปตั้งค่าฝั่ง server ของ U.Perfect อย่างปลอดภัย การมีช่องกรอกค่าใน Dashboard
ไม่ถือว่าเชื่อมต่อสำเร็จ และห้ามวาง token, secret หรือ PIN ใน browser, chat,
Git หรือไฟล์เอกสาร

ใช้ [แบบฟอร์มขอสิทธิ์และอนุมัติ Provider ภาษาไทย](PROVIDER-APPROVAL-FORM_TH.md)
สำหรับเก็บเฉพาะ identifiers, scope, callback, ผู้อนุมัติ และหลักฐานที่ลบ secret
แล้ว แบบฟอร์มนี้ไม่ใช่ที่เก็บ credential

## 1. ภาพรวมขั้นตอนร่วม

1. เจ้าของบัญชีเข้าสู่ portal ทางการด้วยบัญชีธุรกิจของตนเอง
2. สร้าง app/channel และเลือก product หรือ scope ที่ต้องใช้จริง
3. ตั้ง callback/webhook เป็น HTTPS ที่เข้าถึงจาก provider ได้
4. เก็บ credential ใน environment ของ server เท่านั้น
5. ทดสอบการ verify, รับ event, ตอบกลับ และ idempotency
6. ตรวจ `GET /api/integrations` และหน้า **Channels** ว่าสถานะตรงกับหลักฐาน
7. ทดสอบข้อความ/ออเดอร์ใน sandbox หรือบัญชีทดสอบก่อนเปิดใช้งานจริง
8. บันทึกวันหมดอายุ ผู้ดูแล และแผน rotate/revoke ในระบบภายใน

### ขอบเขต local-only

ระบบปัจจุบัน bind ที่ `192.168.74.130:18765` และใช้ Ollama ที่
`http://192.168.74.130:11434` เท่านั้นสำหรับ AI ภายใน ค่า provider ภายนอกยัง
ไม่ถูกใส่ไว้ใน local profile และสถานะจะไม่กลายเป็น `configured` จากการเปิดหน้า
Dashboard อย่างเดียว

### ค่าที่ต้องอยู่ server-side

ห้ามใส่ค่าต่อไปนี้ใน frontend, PWA cache, issue, PR, screenshot หรือ commit:

- access token, refresh token, client secret, partner key, channel secret
- webhook verify token ที่ใช้เป็น shared secret
- GPG PIN, passphrase, private key หรือไฟล์ credential

<a id="facebook-messenger-meta"></a>
## 2. Facebook Messenger / Meta

### Portal ทางการ

- ภาพรวม Messenger Platform: <https://developers.facebook.com/docs/messenger-platform/overview/>
- Webhooks: <https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks>
- Quick start: <https://developers.facebook.com/docs/messenger-platform/getting-started/quick-start/>

### สิ่งที่ต้องมี

- Meta Developer account และ Business ที่ยืนยันตามเงื่อนไขของ Meta
- Meta App ที่เปิด use case ของ Messenger
- Facebook Page ของ U.Perfect และสิทธิ์แอดมิน/ผู้พัฒนา
- Page access token ที่ถูกออกให้กับ Page
- webhook verify token ที่เราสร้างเองและเก็บไว้ server-side

### ขั้นตอน

1. เปิด Meta for Developers และสร้าง App แบบที่รองรับ Messenger/Business
2. เพิ่ม Messenger product/use case ให้กับ App
3. เลือก Page `@spookyuperfect` หรือ Page ที่เจ้าของบัญชียืนยัน
4. ออก Page access token ใน App Dashboard แล้วเก็บใน
   `FACEBOOK_PAGE_ACCESS_TOKEN`
5. สร้าง random verify token ฝั่ง server แล้วเก็บใน
   `FACEBOOK_VERIFY_TOKEN`
6. ตั้ง callback URL ของ adapter ที่ HTTPS และเปิดรับ event ที่จำเป็น เช่น
   message และ postback ตามสิทธิ์ที่ Meta อนุมัติ
7. Subscribe Page ให้กับ App และตรวจว่า Page subscription สำเร็จ
8. ส่งข้อความจากบัญชีทดสอบภายใน policy ของ Meta แล้วตรวจ inbound, reply,
   duplicate event และ human takeover
9. ทำ App Review/Business Verification เมื่อ scope หรือ production access
   ของ Meta กำหนดให้ทำ

### ค่าที่ map เข้าระบบ

| ความหมาย | Environment | หมายเหตุ |
| --- | --- | --- |
| Page access token | `FACEBOOK_PAGE_ACCESS_TOKEN` | secret; server-only |
| webhook verify token | `FACEBOOK_VERIFY_TOKEN` | shared secret; server-only |
| Page URL | workspace setting `facebook_page_url` | เป็น reference ไม่ใช่ proof of connection |

### Gate ของ U.Perfect

Route local test ปัจจุบันคือ `POST /api/webhooks/facebook` และรับ normalized
payload เช่น `event_id`, `customer_id`, `text` เมื่อมี
`X-Hub-Signature-256: sha256=<hex>` ที่คำนวณจาก raw body ด้วย
`FACEBOOK_APP_SECRET` เท่านั้น นี่ไม่ใช่ raw Meta adapter; adapter server-side
ยังต้องตรวจ signature/state ของ Meta ก่อนรับ traffic จริง

<a id="tiktok-shop-open-platform"></a>
## 3. TikTok Shop Open Platform

### Portal ทางการ

- สร้างแอปใน Partner Center: <https://partner.tiktokshop.com/docv2/page/create-your-app>
- OAuth client: <https://partner.tiktokshop.com/docv2/page/create-tts-app-oauth-client>
- Authorization guide: <https://partner.tiktokshop.com/docv2/page/authorization-guide-202309>
- Authorization overview/review: <https://partner.tiktokshop.com/docv2/page/authorization-overview-202407>
- Developer guide: <https://partner.tiktokshop.com/docv2/page/tts-developer-guide>
- Webhook configuration guide: <https://partner.tiktokshop.com/docv2/page/configuration-guide>
- Thailand/ROW authorization ให้ตรวจ label และ region ปัจจุบันใน Partner Center

### สิ่งที่ต้องมี

- TikTok Shop Partner Center account
- app/service ที่ได้รับอนุมัติสำหรับ shop และ API product ที่ต้องใช้
- `service_id`, `app_key`, `app_secret`
- seller/shop authorization และ authorization code
- callback URL ที่จดทะเบียนใน portal
- refresh token ที่เก็บใน server

### ขั้นตอน

1. สร้าง app ใน Partner Center และเลือก API products/scopes ที่เกี่ยวข้องกับ
   shop, order และ customer communication ตามสิทธิ์ที่เปิดจริง
2. คัดลอก `service_id`, `app_key` และสร้าง/เก็บ `app_secret` ในระบบ secret
   ของ server
3. ให้เจ้าของร้าน authorize shop ผ่าน authorization URL ที่ Partner Center
   แสดงสำหรับ region ของบัญชี เช่น ROW/Thailand
4. รับ `auth_code` ผ่าน callback ที่ลงทะเบียนไว้ โดยไม่เขียน code ลง log
5. แลก code ที่ token endpoint ของ TikTok Shop Open Platform แล้วเก็บ access
   token และ refresh token server-side
6. ตั้ง webhook ในเมนู Developing/Basic information ด้วย HTTPS/TLS 1.2
   และ domain ที่ provider รองรับ หลีกเลี่ยง IP/port ตรงตามกฎของ portal
7. ตรวจ Authorization header/signature และตอบ HTTP status ภายในเวลาที่ portal
   กำหนด ก่อนส่ง event เข้าระบบ normalized webhook
8. ทดสอบ refresh token, rate limit, duplicate event, failed delivery และ
   human takeover ด้วย shop test ก่อนเปิดใช้งานจริง

### Token flow ที่ต้องรักษา

- authorization code ใช้ครั้งเดียวและมีอายุสั้น
- ตาม authorization guide ปัจจุบัน `auth_code` มีอายุ 30 นาทีและใช้ได้ครั้งเดียว
  ให้ตรวจ portal อีกครั้งเมื่อ policy เปลี่ยน
- access token ใช้เรียก API ตาม scope
- refresh token ใช้ขอ access token ใหม่และต้อง rotate/เก็บอย่างปลอดภัย
- token endpoint ที่เอกสาร TikTok Shop ปัจจุบันระบุคือ
  `https://auth.tiktok-shops.com/api/v2/token/get` และ refresh endpoint
  `https://auth.tiktok-shops.com/api/v2/token/refresh`; ให้ตรวจ region/API version
  ใน portal ก่อนเรียกจริง
- ห้าม hard-code token ใน source หรือหน้า Settings

### ค่าที่ map เข้าระบบ

| ความหมาย | Environment | หมายเหตุ |
| --- | --- | --- |
| app key | `TIKTOK_APP_KEY` | identifier; server-side config |
| app secret | `TIKTOK_APP_SECRET` | secret; server-only |
| refresh token | `TIKTOK_REFRESH_TOKEN` | secret; server-only |

หากเพิ่ม OAuth callback adapter ให้ใช้ redirect URL ที่ลงทะเบียนใน portal และ
เก็บค่า callback ในระบบ deployment secret/config ที่เหมาะสม ไม่ใส่ใน frontend

### Gate ของ U.Perfect

`POST /api/webhooks/tiktok` ปัจจุบันเป็น normalized local test boundary เท่านั้น
ต้องมี `X-UPerfect-Webhook-Signature: sha256=<hex>` จาก raw body ด้วย
`TIKTOK_WEBHOOK_SECRET` และ `event_id` เพื่อให้ idempotency ทำงาน ยังไม่ควรผูก
raw TikTok webhook เข้ากับ route นี้โดยตรง

<a id="shopee-open-platform"></a>
## 4. Shopee Open Platform

### Portal ทางการ

- Shopee Open Platform: <https://open.shopee.com/>
- Partner API host ที่พบใน integration setup: <https://partner.shopeemobile.com/>

ชื่อเมนู, scope และขั้นตอนอนุมัติอาจเปลี่ยนตามประเทศและรุ่น API ให้ยึด
เอกสาร/console ที่แสดงกับบัญชีเจ้าของร้าน ณ วันที่ตั้งค่าจริง

### สิ่งที่ต้องมี

- Shopee Open Platform/Partner account
- Partner ID และ Partner Key
- Shop ID ที่จะ authorize
- callback URL และ authorization code ตาม flow ที่ portal ออกให้
- access token/refresh token หรือค่าที่ portal กำหนดสำหรับ API รุ่นนั้น
- สิทธิ์ API ที่ครอบคลุม order, item และ customer service/chat หากต้องใช้แชท

### ขั้นตอน

1. เข้าสู่ Open Platform ด้วยบัญชี partner ที่ได้รับอนุมัติ
2. สร้าง application และเลือกประเทศ/region ของร้าน
3. เก็บ Partner ID เป็น `SHOPEE_PARTNER_ID` และ Partner Key เป็น
   `SHOPEE_PARTNER_KEY` ใน server secret store เท่านั้น
4. เพิ่ม/ลงทะเบียน callback URL และให้เจ้าของร้าน authorize Shop ID
5. รับ authorization code และ shop identifier บน callback ที่ตรวจสอบ state
6. แลก code ตาม API version ปัจจุบัน แล้วเก็บ token ที่ได้ server-side
7. สร้าง request signature ตามกติกาของ endpoint และตรวจ timestamp/expiry
8. เปิดเฉพาะ scope ที่ใช้จริง โดยเฉพาะ customer service/chat หากมีสิทธิ์
   แยกจาก order/item
9. ทดสอบ shop authorization, order read, chat send/receive, rate limit และ
   duplicate event ในร้านทดสอบ

### ค่าที่ map เข้าระบบ

| ความหมาย | Environment | หมายเหตุ |
| --- | --- | --- |
| Partner ID | `SHOPEE_PARTNER_ID` | identifier |
| Partner Key | `SHOPEE_PARTNER_KEY` | secret; server-only |
| Shop ID | `SHOPEE_SHOP_ID` | account scope; verify with owner |

### Gate ของ U.Perfect

`POST /api/webhooks/shopee` เป็น normalized local test boundary เช่นเดียวกับ
provider อื่น ต้องผ่าน `X-UPerfect-Webhook-Signature: sha256=<hex>` จาก raw body
ด้วย `SHOPEE_WEBHOOK_SECRET` และ event idempotency ก่อน ระบบยังไม่ได้กล่าวอ้างว่า
Shopee chat/order adapter production พร้อมใช้งาน

<a id="line-messaging-api"></a>
## 5. LINE Messaging API

### Portal ทางการ

- Building a bot: <https://developers.line.biz/en/docs/messaging-api/building-bot/>
- Channel access token: <https://developers.line.biz/en/docs/basics/channel-access-token/>
- Messaging API reference: <https://developers.line.biz/en/reference/messaging-api/>

### ขอบเขต release นี้

U.Perfect มี retryable notification outbox สำหรับแจ้งเหตุการณ์ออเดอร์ที่
ยืนยันแล้วไปยัง LINE และมี normalized inbound boundary ที่ตรวจ
`X-Line-Signature` ด้วย `LINE_CHANNEL_SECRET` จาก raw body ปัจจุบันยังไม่มี
inbound LINE chatbot adapter production และยังไม่ควรนำ
`LINE_CHANNEL_ACCESS_TOKEN` ไปใช้ตอบแชทลูกค้าโดยอัตโนมัติ

### หมายเหตุ compatibility จาก LINE Developers เดือนกรกฎาคม 2026

ตรวจสอบเมื่อวันที่ 2026-08-10 จาก [ดัชนีข่าว LINE Developers เดือนกรกฎาคม 2026](https://developers.line.biz/en/news/2026/07):

- [LIFF v2.29.2 (2026-07-31)](https://developers.line.biz/en/news/2026/07/31/release-liff-2-29-2/)
  ออก release โดยไม่มี feature change ที่ต้องปรับใช้ U.Perfect ยังไม่ได้ใช้
  LIFF ใน release นี้ จึงไม่ต้องเปลี่ยน runtime configuration
- [Rich menu statistics (2026-07-01)](https://developers.line.biz/en/news/2026/07/01/rich-menu-insight/)
  และ [การปรับปรุงค่าบริการ LINE MINI App in-app purchase](https://developers.line.biz/en/news/2026/07/01/iap-service-fees/)
  อยู่นอกขอบเขตปัจจุบัน U.Perfect ยังไม่มี rich-menu analytics, LINE MINI App
  หรือ LINE in-app purchase integration ใน release นี้
- [เหตุขัดข้อง LINE Platform วันที่ 2026-07-28](https://developers.line.biz/en/news/2026/07/28/messaging-api-outage/)
  ได้รับการแก้ไขแล้ว หากเพิ่ม LINE sender ในอนาคตต้องรักษา idempotency ของ
  outbox และใช้ `X-Line-Retry-Key` ตามเอกสาร LINE เมื่อเป็น 5xx/timeout ที่
  endpoint รองรับ ห้าม retry แบบส่งข้อความซ้ำโดยไม่ควบคุม

หมายเหตุนี้เป็นแนวทาง compatibility ไม่ใช่หลักฐานว่า LINE account ตั้งค่าแล้ว
หรือผ่านการ verify แล้ว ให้ตรวจดัชนีข่าวและ API reference ทางการอีกครั้งก่อนเปิด
ใช้ผลิตภัณฑ์หรือ transport ใหม่ของ LINE

### ขั้นตอนสำหรับ outbound notification

1. สร้าง Messaging API channel ใน LINE Developers Console
2. เพิ่ม Official Account และกำหนดผู้รับที่ถูกต้อง
3. ออก channel access token โดยเลือกอายุ/ประเภทที่เหมาะกับการ rotate
4. เก็บ token ใน `LINE_CHANNEL_ACCESS_TOKEN`
5. เก็บ user/group/room destination ใน `LINE_ADMIN_DESTINATION`
6. ทดสอบ push message จาก server และตรวจ outbox ว่า pending เปลี่ยนเป็น sent
   หรือ failed แบบ retryable
7. ตั้ง alert เมื่อ token ถูก revoke, destination ใช้ไม่ได้ หรือจำนวน failed
   เพิ่มขึ้น

### ขั้นตอนสำหรับ inbound ในอนาคต

1. สร้าง/ตรวจ `LINE_CHANNEL_SECRET` ในระบบ server secret
2. ตั้ง HTTPS webhook URL ใน LINE Developers Console
3. Verify endpoint และเปิด **Use webhook**
4. ตรวจ `x-line-signature` ด้วย channel secret ก่อน normalize event
5. ตรวจ reply token/เวลาใช้งานและใช้ reply/push endpoint ตาม event

### ค่าที่ map เข้าระบบ

| ความหมาย | Environment | สถานะ |
| --- | --- | --- |
| channel access token | `LINE_CHANNEL_ACCESS_TOKEN` | ใช้กับ outbox เมื่อ owner ตั้งค่า |
| admin destination | `LINE_ADMIN_DESTINATION` | ใช้กับ outbox |
| channel secret | `LINE_CHANNEL_SECRET` | HMAC ของ normalized/inbound boundary; server-only |

## 6. ตรวจผลหลังตั้งค่า

### Dashboard

1. เปิด **Channels**
2. ตรวจ provider ที่ต้องการและอ่านข้อความ setup note
3. เปิดคู่มือ TH/EN จาก provider card
4. ตรวจว่า browser ไม่เห็น token หรือ secret
5. ใช้ Settings เปลี่ยนภาษาได้ทันทีโดยไม่เปลี่ยนค่าความลับ

### API

```bash
curl http://192.168.74.130:18765/api/health
curl http://192.168.74.130:18765/api/integrations
curl http://192.168.74.130:18765/api/integration-guides
curl http://192.168.74.130:18765/api/sales-assets
```

ค่าที่ชื่อ `configured` หมายถึง environment ที่จำเป็นมีค่าเท่านั้น ไม่ได้
หมายถึง token ใช้งานได้จริงเสมอไป ต้องผ่าน provider ping, webhook delivery,
permission check และ test transaction ก่อนเปลี่ยนสถานะเป็น `verified`

## 7. Checklist อนุมัติ production

- [ ] เจ้าของบัญชีอนุมัติ app และ scope แล้ว
- [ ] callback/webhook ใช้ HTTPS และ domain ถูกต้อง
- [ ] token/secret อยู่ใน server secret store ไม่อยู่ใน git
- [ ] provider signature/state/nonce ตรวจที่ adapter server-side
- [ ] duplicate event ถูกละทิ้งอย่างถูกต้อง
- [ ] rate limit และ retry/backoff มีหลักฐานจากการทดสอบ
- [ ] human takeover และ stop automation ทดสอบแล้ว
- [ ] payment evidence ยังเป็น `pending_review` จนผู้มีอำนาจอนุมัติ
- [ ] LINE notification outbox มี owner และแผน rotate token
- [ ] มี rollback/revoke contact และบันทึกเวลาเปิดใช้งาน

## 8. แบบฟอร์มอนุมัติและหลักฐานแบบละเอียด

กรอก [Provider Approval Form ภาษาไทย](PROVIDER-APPROVAL-FORM_TH.md) ให้ครบ
ทุก provider ที่ต้องการเปิดใช้ โดยเฉพาะ owner, region, app/channel ID, scope,
exact callback/webhook URL, review/ticket ID, test evidence และผู้รับผิดชอบ
rollback แบบฟอร์มจะช่วยแยก `configured` (environment ครบ) ออกจาก `verified`
(มี provider delivery และ server-side verification จริง)

### ข้อจำกัด callback ของ local-only

`192.168.74.130` ใช้สำหรับ local runtime และ normalized test เท่านั้น ผู้ให้บริการ
ภายนอกไม่ควรเรียก callback/webhook เข้ามาที่ private LAN IP โดยตรง ก่อนเปิดใช้จริง
ต้องมี public HTTPS adapter ที่ตรวจ provider signature, OAuth state/nonce,
timestamp, retry และ duplicate event แล้วจึงค่อยเชื่อมเข้าระบบภายใน
