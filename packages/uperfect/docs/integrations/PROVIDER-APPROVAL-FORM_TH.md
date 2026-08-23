# แบบฟอร์มขอสิทธิ์และอนุมัติ Provider / U.Perfect

เอกสารนี้เป็น **แบบฟอร์มข้อมูลและหลักฐาน** สำหรับเจ้าของบัญชีธุรกิจของ
Facebook/Meta, TikTok Shop, Shopee และ LINE ใช้กรอกในระบบภายในหรือ private
GitHub issue เท่านั้น ห้ามใส่ token, secret, PIN, passphrase, QR ชำระเงิน หรือ
ไฟล์ credential ลงในแบบฟอร์ม

## วิธีใช้

1. เจ้าของบัญชีกรอกส่วนข้อมูลระบุตัวตนและเลือก provider ที่ต้องการ
2. ดำเนินการใน portal ทางการด้วยบัญชีของเจ้าของธุรกิจ
3. แนบเฉพาะ URL หลักฐาน, ticket/review ID, screenshot ที่ลบ secret แล้ว และ
   timestamp; ห้ามแนบค่าความลับ
4. ผู้พัฒนาเพิ่มค่า secret ใน environment ของ server เท่านั้น แล้วทดสอบตาม
   acceptance checklist
5. เปลี่ยนสถานะจาก `unconfigured` เป็น `configured` เมื่อ environment ครบ
   และเปลี่ยนเป็น `verified` เมื่อมีหลักฐาน provider test ครบทุกข้อ

## สถานะของ release ปัจจุบัน

- U.Perfect local runtime: `http://192.168.74.130:18765`
- Local AI: `http://192.168.74.130:11434` และ `zCoder:latest`
- สถานะ provider เริ่มต้น: `unconfigured`
- route `POST /api/webhooks/{provider}` เป็น normalized local test ที่ตรวจ HMAC
  จาก raw body เท่านั้น
- ห้ามใช้ `192.168.74.130` เป็น callback/webhook ของ provider ภายนอก เพราะ
  เป็น private LAN address; provider ต้องเข้าถึง HTTPS adapter ที่มี certificate
  และตรวจลายเซ็นได้
- การมี `uperfect.zeaz.dev` หรือการเปิดหน้า Dashboard ไม่ใช่หลักฐานว่า provider
  อนุมัติหรือเชื่อมต่อแล้ว

## 1. ข้อมูลเจ้าของบัญชีและคำขอร่วม

| รายการ | กรอกค่า |
| --- | --- |
| ชื่อบริษัท/ร้าน | <!-- กรอก --> |
| ชื่อผู้อนุมัติ | <!-- กรอก --> |
| อีเมลธุรกิจ | <!-- กรอก --> |
| ผู้รับผิดชอบเทคนิค | <!-- กรอก --> |
| วันที่ขอ | <!-- YYYY-MM-DD --> |
| วันที่ต้องการเปิดใช้งาน | <!-- YYYY-MM-DD --> |
| ประเทศ/ตลาด | Thailand / อื่น ๆ: <!-- กรอก --> |
| Environment | sandbox / test shop / production |
| เลือก provider | Facebook / TikTok / Shopee / LINE |
| เป้าหมาย | รับข้อความ / ตอบข้อความ / อ่านออเดอร์ / แจ้งเตือน LINE |

### หลักการขอ scope

- ขอเฉพาะ scope ที่ตรงกับงานที่เลือก ไม่ขอสิทธิ์กว้างเพื่อทดลอง
- แยกสิทธิ์อ่านข้อความ, ตอบข้อความ, อ่านออเดอร์, fulfillment และ post/comment
- บันทึกชื่อ scope ตามที่ portal แสดงจริง ไม่เดาจากชื่อในเอกสารเก่า
- จดเหตุผลทางธุรกิจของทุก scope เพื่อใช้ตอบ App Review

| Scope/API product | เหตุผลทางธุรกิจ | ต้องใช้ใน release นี้หรือไม่ |
| --- | --- | --- |
| <!-- กรอกชื่อจริงจาก portal --> | <!-- กรอก --> | yes / no |
| <!-- กรอกชื่อจริงจาก portal --> | <!-- กรอก --> | yes / no |

## 2. Callback, webhook และ security gate

| รายการ | ค่าที่อนุมัติ/ตรวจสอบแล้ว |
| --- | --- |
| Public HTTPS adapter URL | <!-- ห้ามใช้ LAN IP --> |
| OAuth redirect/callback URL | <!-- exact URL รวม path --> |
| Provider webhook URL | <!-- exact URL รวม path --> |
| TLS certificate owner/expiry | <!-- กรอก --> |
| Signature verification implemented | yes / no |
| OAuth state/nonce validation implemented | yes / no / not applicable |
| Event idempotency key | <!-- event ID ที่ provider ให้ --> |
| Retry/backoff and rate limit plan | <!-- ลิงก์ runbook --> |
| Raw payload retention policy | <!-- กรอกอายุ/การลบ --> |

`POST /api/webhooks/{provider}` ของระบบปัจจุบันรับเฉพาะ normalized test payload
ที่มี provider-specific HMAC header จาก test ฝั่ง server ห้ามนำ raw payload จาก
provider มายิง route นี้โดยตรง

<a id="facebook-messenger-meta"></a>
## 3. Facebook Messenger / Meta

### Portal และรายการที่ต้องกรอก

- Portal: <https://developers.facebook.com/>
- Messenger overview: <https://developers.facebook.com/docs/messenger-platform/overview/>
- Quick start: <https://developers.facebook.com/docs/messenger-platform/getting-started/quick-start/>
- Webhooks: <https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks>

| รายการ | ค่าที่กรอกได้โดยไม่เปิดเผย secret |
| --- | --- |
| Meta Business name/ID | <!-- กรอก identifier --> |
| Meta App name/ID | <!-- กรอก identifier --> |
| App mode | Development / Live |
| Messenger use case/product | <!-- ชื่อที่ portal แสดง --> |
| Facebook Page name/ID | `@spookyuperfect` / <!-- Page ID --> |
| Page owner/admin confirmed | yes / no |
| Requested permissions | <!-- ชื่อจริงจาก portal --> |
| App Review/Business Verification case | <!-- URL หรือ case ID --> |
| Test accounts/Page roles | <!-- ระบุแบบไม่ใส่ password --> |
| Callback/webhook URL | <!-- exact public HTTPS URL --> |

### ขั้นตอนอนุมัติ

1. เจ้าของธุรกิจเข้าสู่ Meta for Developers และเลือก Business/App ที่ถูกต้อง
2. เพิ่ม Messenger use case/product ตามที่ portal ปัจจุบันแสดง
3. เชื่อม Page `@spookyuperfect` และตรวจบทบาทผู้ดูแล/ผู้พัฒนา
4. จด App ID, Business ID, Page ID และ permission names ลงแบบฟอร์ม
5. ลงทะเบียน callback/webhook HTTPS ของ adapter ที่ตรวจ signature และ verify
   request ฝั่ง server; ห้ามชี้ไปที่ `192.168.74.130`
6. ทดสอบด้วยบัญชี/Page role ก่อน แล้วส่ง App Review หรือ Business Verification
   เมื่อ scope/โหมด Live ของ Meta ขอหลักฐาน
7. หลังอนุมัติ ผู้ดูแล server ออก Page access token และเก็บไว้ใน
   `FACEBOOK_PAGE_ACCESS_TOKEN` เท่านั้น; สร้างค่า verify token ใหม่ไว้ใน
   `FACEBOOK_VERIFY_TOKEN`

### หลักฐานที่ต้องแนบแบบไม่ลับ

- App/Business/Page identifiers
- รายการ permission ที่อนุมัติและวันหมดอายุถ้ามี
- Review case/status URL หรือ screenshot ที่ปิด token แล้ว
- webhook verification result และ inbound/outbound test ID
- duplicate-event และ human-takeover test result

### Environment mapping

| Portal value | U.Perfect environment | ห้ามแสดงที่ใด |
| --- | --- | --- |
| Page access token | `FACEBOOK_PAGE_ACCESS_TOKEN` | browser, GitHub, log |
| Server-generated verify token | `FACEBOOK_VERIFY_TOKEN` | browser, GitHub, log |
| Page URL/reference | `facebook_page_url` workspace setting | ใช้เป็น reference เท่านั้น |

<a id="tiktok-shop-open-platform"></a>
## 4. TikTok Shop Open Platform

### Portal และรายการที่ต้องกรอก

- Partner Center: <https://partner.tiktokshop.com/>
- Create an app: <https://partner.tiktokshop.com/docv2/page/create-your-app>
- OAuth client: <https://partner.tiktokshop.com/docv2/page/create-tts-app-oauth-client>
- Authorization guide: <https://partner.tiktokshop.com/docv2/page/authorization-guide-202309>
- Authorization overview: <https://partner.tiktokshop.com/docv2/page/authorization-overview-202407>
- Webhook configuration: <https://partner.tiktokshop.com/docv2/page/configuration-guide>

| รายการ | ค่าที่กรอกได้โดยไม่เปิดเผย secret |
| --- | --- |
| Partner Center account/organization | <!-- identifier --> |
| App type | Public / Custom |
| Market/region | Thailand / ROW / <!-- portal value --> |
| App/service name | <!-- กรอก --> |
| `service_id` | <!-- identifier --> |
| `app_key` | <!-- identifier --> |
| API products/scopes | <!-- ชื่อจริงจาก portal --> |
| Development shop/test seller | <!-- identifier --> |
| Seller/shop authorization status | requested / approved |
| Redirect URL | <!-- exact registered URL --> |
| Webhook URL | <!-- public HTTPS domain; never LAN IP --> |
| Enrollment/review case | <!-- case ID/status URL --> |

### ขั้นตอนอนุมัติและ OAuth

1. ลงทะเบียน developer/Partner Center account และเลือก market/region ให้ตรง
   กับ seller ไทย
2. สร้าง app/service เลือก Public หรือ Custom ตามการใช้งาน และเลือก API
   products/scopes ที่จำเป็นจริง
3. จด `service_id` และ `app_key`; ห้ามจด `app_secret` ลงแบบฟอร์มนี้
4. ลงทะเบียน redirect URL แบบ exact match และเตรียม HTTPS adapter ที่ตรวจ
   `state`/nonce
5. ใช้ authorization link ที่ Partner Center สร้างให้ seller อนุมัติ shop
6. รับ `auth_code` ที่ callback แล้วแลก token ฝั่ง serverเท่านั้น; authorization
   guide ปัจจุบันระบุว่า code มีอายุ 30 นาทีและใช้ครั้งเดียว ให้ตรวจ policy ใน
   Partner Center ซ้ำก่อนใช้งานจริง และห้ามใส่ log หรือส่งต่อในแชต
7. เก็บ app key/secret และ refresh token ใน server environment ตาม mapping
8. ตั้ง webhook ใน Developing/Basic information ตามกติกา HTTPS/TLS และตรวจ
   `Authorization`/signature ก่อน normalize event
9. ส่งหลักฐาน scope/enrollment/app review ตามที่ public app หรือ connector
   flow ของ portal กำหนดก่อนเปิด production

### Environment mapping

| Portal value | U.Perfect environment | หมายเหตุ |
| --- | --- | --- |
| App key | `TIKTOK_APP_KEY` | identifier ฝั่ง server |
| App secret | `TIKTOK_APP_SECRET` | secret; ไม่ใส่เอกสาร |
| Refresh token | `TIKTOK_REFRESH_TOKEN` | secret; rotate ตาม portal |
| Registered redirect URL | adapter deployment config | ยังไม่มีใน local-only normalized release |

### หลักฐานที่ต้องแนบ

- App type, market, `service_id`, `app_key` และ requested scope list
- test shop/seller authorization result
- redirect/webhook verification result
- enrollment/review status หรือ ticket ID
- token exchange/refresh test ที่แสดงเฉพาะ status และ expiry แบบ masked
- rate-limit, duplicate-event และ failed-delivery test

<a id="shopee-open-platform"></a>
## 5. Shopee Open Platform

### Portal และรายการที่ต้องกรอก

- Open Platform: <https://open.shopee.com/>
- Partner API host/reference: <https://partner.shopeemobile.com/>
- ใช้เอกสารและเมนูที่แสดงกับ region/API version ของบัญชีจริงเป็นหลัก

| รายการ | ค่าที่กรอกได้โดยไม่เปิดเผย secret |
| --- | --- |
| Partner organization/account | <!-- identifier --> |
| App name/ID | <!-- identifier ถ้า portal แสดง --> |
| Region/country | Thailand / <!-- portal value --> |
| Partner ID | <!-- identifier --> |
| Shop ID(s) | <!-- identifier --> |
| Requested API modules | order / item / chat / fulfillment / อื่น ๆ |
| Requested scopes | <!-- ชื่อจริงจาก portal --> |
| Shop owner authorization | requested / approved |
| Redirect/callback URL | <!-- exact registered URL --> |
| Webhook URL | <!-- public HTTPS adapter URL --> |
| API version | <!-- portal value --> |
| Review/ticket status | <!-- ID/URL --> |

### ขั้นตอนอนุมัติและ request signing

1. เจ้าของบัญชีเข้าสู่ Shopee Open Platform ด้วย partner account ที่ถูกต้อง
2. สร้าง application ตาม region/country ของร้าน และอ่าน API module ที่เปิดให้
3. จด Partner ID, Shop ID และชื่อ scope; ห้ามใส่ Partner Key ในแบบฟอร์ม
4. ลงทะเบียน callback URL แบบ exact match และให้เจ้าของร้าน authorize Shop ID
5. ใช้ authorization code/token flow ตาม API version ที่ portal ให้ในปัจจุบัน
6. เก็บ Partner ID/Key และ token ที่เกี่ยวข้องใน server environment เท่านั้น
7. ทำ HMAC/request signature ตาม endpoint reference โดยตรวจ timestamp และ
   expiry ใน provider adapter ก่อนส่งต่อเข้าระบบ
8. ขอหรือเปิดเฉพาะ module ที่ใช้งานจริง เช่น order/item หรือ customer service
   chat; หาก chat ต้องผ่าน permission/approval แยก ให้บันทึกหลักฐาน
9. ทดสอบ read order, item, chat send/receive, rate limit และ duplicate event
   ในร้านทดสอบก่อนเปิด production

### Environment mapping

| Portal value | U.Perfect environment | หมายเหตุ |
| --- | --- | --- |
| Partner ID | `SHOPEE_PARTNER_ID` | identifier |
| Partner Key | `SHOPEE_PARTNER_KEY` | secret; ไม่ใส่เอกสาร |
| Shop ID | `SHOPEE_SHOP_ID` | scope ของร้าน; เจ้าของต้องยืนยัน |
| Registered redirect URL | adapter deployment config | ยังไม่มีใน local-only normalized release |

### หลักฐานที่ต้องแนบ

- Partner/app/region/API version identifiers
- Shop authorization result และ scope list
- callback/webhook verification result
- masked API health/signature test และ response status
- order/item/chat test evidence ที่ไม่มีข้อมูลลูกค้าหรือ secret
- rate-limit, retry, duplicate-event และ revoke/rotate runbook

<a id="line-messaging-api"></a>
## 6. LINE Messaging API

### Portal และรายการที่ต้องกรอก

- Building a bot: <https://developers.line.biz/en/docs/messaging-api/building-bot/>
- Channel access token: <https://developers.line.biz/en/docs/basics/channel-access-token/>
- Webhook receive: <https://developers.line.biz/en/docs/messaging-api/receiving-messages/>
- API reference: <https://developers.line.biz/en/reference/messaging-api/>

| รายการ | ค่าที่กรอกได้โดยไม่เปิดเผย secret |
| --- | --- |
| LINE Developers provider | <!-- identifier/name --> |
| Messaging API channel name/ID | <!-- identifier --> |
| Official Account name/ID | <!-- identifier --> |
| Token type | v2.1 / stateless / short-lived / long-lived |
| Token expiry/rotation owner | <!-- กรอก --> |
| Admin destination type | user / group / room |
| Admin destination ID | <!-- identifier; ไม่ใช่ token --> |
| Webhook URL (inbound future) | <!-- public HTTPS adapter --> |
| Verify result / Use webhook | pending / success / enabled |
| Review/ticket status | <!-- กรอก --> |

### ขั้นตอน outbound แจ้งเตือน

1. สร้าง Messaging API channel ใน LINE Developers Console และเชื่อม Official
   Account ที่ถูกต้อง
2. ออก channel access token ชนิดและอายุที่เหมาะกับการ rotate; แนวทาง LINE
   แนะนำ token v2.1 สำหรับการใช้งาน Messaging API
3. เก็บ token ใน `LINE_CHANNEL_ACCESS_TOKEN` ฝั่ง server เท่านั้น
4. หา user/group/room destination จาก flow ที่ได้รับอนุญาต แล้วเก็บใน
   `LINE_ADMIN_DESTINATION`; ห้ามเดา destination จากชื่อผู้ใช้
5. ทดสอบ push message แบบ internal และตรวจ LINE notification outbox
6. จดวัน rotate/revoke และผู้รับผิดชอบ หาก token รั่วให้ revoke ทันที

### ขั้นตอน inbound ในอนาคต

1. ตั้ง public HTTPS webhook ที่มี certificate จาก CA ที่ browser เชื่อถือได้
2. กรอก URL ใน Messaging API tab แล้วกด Verify; เมื่อสำเร็จจึงเปิด **Use webhook**
3. เก็บ channel secret ในระบบ secret store และตรวจ `x-line-signature` ก่อน
   normalize event
4. เพิ่ม Official Account เป็นเพื่อนเพื่อทดสอบ follow/message event
5. ปิด Greeting/Auto-reply ของ LINE Official Account Manager หากการตอบจะ
   ควบคุมโดย Messaging API เพื่อไม่ให้ตอบซ้ำ

### Environment mapping และขอบเขตปัจจุบัน

| Portal value | U.Perfect environment | สถานะ |
| --- | --- | --- |
| Channel access token | `LINE_CHANNEL_ACCESS_TOKEN` | ใช้กับ outbound outbox เมื่อ owner ตั้งค่า |
| Admin destination | `LINE_ADMIN_DESTINATION` | ใช้กับ outbound outbox |
| Channel secret | `LINE_CHANNEL_SECRET` | HMAC ของ inbound boundary; server-only |

ระบบ release นี้ยังไม่เปิด LINE inbound chatbot และไม่อ้างว่า LINE ส่งจริง
จนกว่าจะมี token, destination, sender transport และหลักฐาน test ครบ

## 7. Final approval และ sign-off

| Gate | Owner | หลักฐาน/ลิงก์ | สถานะ |
| --- | --- | --- | --- |
| Portal account ownership | <!-- ชื่อ --> | <!-- URL/case --> | pending |
| App/channel created | <!-- ชื่อ --> | <!-- identifier --> | pending |
| Scope approved | <!-- ชื่อ --> | <!-- review evidence --> | pending |
| Redirect/webhook verified | <!-- ชื่อ --> | <!-- test evidence --> | pending |
| Server env configured | <!-- ชื่อ --> | <!-- deploy ID, no secret --> | pending |
| Provider API test passed | <!-- ชื่อ --> | <!-- masked test ID --> | pending |
| Duplicate/retry/rate-limit test | <!-- ชื่อ --> | <!-- runbook --> | pending |
| Human takeover tested | <!-- ชื่อ --> | <!-- test conversation ID --> | pending |
| Rollback/revoke owner assigned | <!-- ชื่อ --> | <!-- runbook --> | pending |

### Owner declaration

ข้าพเจ้ารับรองว่าบัญชีและสิทธิ์ที่ระบุข้างต้นเป็นของธุรกิจที่ได้รับอนุญาต,
scope ถูกขอเท่าที่จำเป็น, callback/webhook ผ่านการตรวจสอบ และ secret จะถูกส่ง
ผ่านช่องทาง server ที่กำหนดเท่านั้น

- ผู้อนุมัติ: <!-- กรอก -->
- วันที่/เวลา UTC: <!-- กรอก -->
- ลายเซ็นหรือ ticket approval: <!-- กรอก -->
- ผู้ตรวจ technical: <!-- กรอก -->
- วันที่ verify: <!-- กรอก -->

สถานะ `verified` ห้ามตั้งจากการกรอกแบบฟอร์มเพียงอย่างเดียว ต้องมี provider
delivery และ server-side verification evidence ครบตาม release checklist
