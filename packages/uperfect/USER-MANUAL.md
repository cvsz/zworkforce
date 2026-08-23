# U.Perfect User Manual / คู่มือผู้ใช้งาน

**Product:** U.Perfect Social Commerce OS
**Audience:** shop operators, chat agents, and staff using the Dashboard
**Languages:** Thai (TH) and English (EN)
**Current address:** `http://192.168.74.130:18765/`

## ภาษาไทย

### 1. เริ่มใช้งาน

1. เชื่อมต่ออุปกรณ์ในเครือข่ายเดียวกับ `192.168.74.130`
2. เปิด `http://192.168.74.130:18765/`
3. หากต้องการใช้งานเหมือนแอป ให้เลือก **Add to Home Screen/Install** จาก browser
4. กดปุ่ม **TH/EN** ที่มุมขวาบนเพื่อเปลี่ยนภาษา
5. กดปุ่ม refresh เมื่อสถานะ API ยังไม่ online

ระบบเป็น responsive PWA ใช้ได้บน Android, iOS, Windows และ desktop browser
แต่การติดตั้ง PWA ไม่ได้เปิดสิทธิ์ให้ browser เห็น token หรือ secret ของร้าน

### 2. เมนูหลัก

- **ภาพรวม:** จำนวนสินค้า บทสนทนา ออเดอร์ งานรอตรวจ และสถานะช่องทาง
- **แชตรวม:** ดูบทสนทนา ส่งข้อความทดสอบเข้า Autobot และเปิด/ปิด human takeover
- **Product Memory:** อ่าน alias, ส่วนผสม, ราคา, promotion และ source listing
- **ออเดอร์:** สร้าง draft order, รับ payment evidence และดูสถานะ review
- **Skills / Agents:** ตรวจความสามารถและขอบเขตการทำงานที่ server รายงาน
- **n8n Automations:** ดู workflow ที่ยังต้องผ่าน account/webhook verification
- **Channels:** ดูสถานะจริงและเปิดคู่มือขอ API หรือแบบฟอร์มอนุมัติ TH/EN
- **Sales Assets:** ดูรูป local, selling points, intent และข้อความ CTA ที่ใช้จริง
- **ตั้งค่า:** แก้โปรไฟล์ร้าน ภาษา โทน Autobot เวลา takeover และ notification preference

### 3. ใช้แชตรวมและปิดการขาย

1. เปิด **แชตรวม** แล้วเลือกบทสนทนาที่มีอยู่ หรือกรอก Customer ID ใหม่
2. ส่งคำถามเกี่ยวกับชื่อสินค้า ส่วนผสม ราคา การจัดส่ง หรือการซื้อ
3. Autobot จะใช้ product memory และ response assets ที่ตรวจสอบแล้ว
4. เมื่อลูกค้าต้องการซื้อ ให้ยืนยันจำนวน ระบบจะช่วยสรุปข้อมูลก่อนสร้าง draft order
5. หากลูกค้าต้องการคุยกับคน ให้เปิด **แอดมินรับช่วง** ระบบจะหยุดตอบอัตโนมัติ
6. หลังลูกค้าส่งสลิป ให้ผู้มีสิทธิ์ตรวจสอบและกดยืนยันจากเมนู **ออเดอร์**

โทนข้อความออกแบบให้เป็นแอดมินที่สุภาพ เป็นมิตร น่ารัก ชวนตัดสินใจ และมี CTA
แต่ระบบจะไม่แต่งราคา สต็อก ค่าส่ง ผลลัพธ์ทางการแพทย์ หรือบอกว่าชำระเงินสำเร็จ
ก่อนผู้มีสิทธิ์ตรวจสอบ

### 4. ดู Sales Assets

หน้า **Sales Assets** แสดง:

- ภาพสินค้าที่อยู่ใน `assets/` ของเครื่องนี้เท่านั้น
- selling points ภาษาไทย/อังกฤษ
- intents เช่น ราคา ส่วนผสม ซื้อ ชำระเงิน ที่อยู่ และ objection
- CTA ปิดการขายตามสถานะสินค้า
- สินค้าที่เป็น `reference_only` หรือราคายังไม่ยืนยัน

ถ้ารูปไม่แสดง ให้ตรวจว่า server ยังทำงานและเปิด path `/assets/...` ได้ ห้ามเปลี่ยน
path เป็น URL ภายนอกโดยไม่ผ่านการตรวจสอบ asset policy

### 5. สร้างออเดอร์และตรวจหลักฐาน

- สินค้าที่ไม่มีราคายืนยันจะไม่ปรากฏในตัวเลือกสร้าง order
- order ใหม่เริ่มที่ `awaiting_payment`
- หลักฐานการชำระเงินเปลี่ยนเป็น `pending_review`
- เฉพาะผู้มีสิทธิ์เท่านั้นที่เปลี่ยนเป็น `confirmed`
- เมื่อยืนยันแล้ว ระบบเขียนเหตุการณ์ลง LINE notification outbox
- worker จะ claim event ด้วย lease, ส่งจาก server และ retry failure ตาม backoff
- การส่ง LINE จริงต้องตั้งค่า LINE ฝั่ง server และยังไม่ส่งจาก browser

### 6. อ่านสถานะช่องทาง

- `Unconfigured/ยังไม่ตั้งค่า`: ยังไม่มีค่าที่จำเป็นฝั่ง server
- `Configured/ตั้งค่าแล้ว`: มีค่าครบตาม environment แต่ยังไม่ใช่หลักฐานว่า API ใช้ได้
- `Degraded/ต้องตรวจสอบ`: service ตอบกลับไม่ครบหรือ local AI หา model ไม่เจอ
- `Verified/ยืนยันแล้ว`: ต้องมีหลักฐาน provider test และ server verification
- `Outbox/รอส่งออก`: เหตุการณ์รอ worker ส่งต่อ

ใน release นี้ Facebook, TikTok Shop, Shopee, LINE, n8n และ Gemini จะยังไม่พร้อม
โดยอัตโนมัติ การเปิดหน้า Dashboard ไม่ได้ authorize บัญชีใด ๆ

### 7. แก้ปัญหาเบื้องต้น

| อาการ | วิธีตรวจ |
| --- | --- |
| API offline | ตรวจ service และกด refresh; ทดสอบ `/api/health` |
| รูปสินค้าไม่ขึ้น | ตรวจไฟล์ใน `assets/` และ path `/assets/` |
| คำตอบไม่ตรงภาษา | กด TH/EN และตรวจ `default_language` ใน Settings |
| บอทไม่ตอบ | ตรวจ Autobot enabled และ human takeover |
| สร้างออเดอร์ไม่ได้ | ตรวจราคา สต็อก และสถานะสินค้าใน Product Memory |
| LINE ไม่ส่ง | ดู Channels, notification outbox และ `uperfect-worker.service`; อย่าใส่ token ใน browser |

### 8. ข้อมูลที่ห้ามส่งเข้าระบบสาธารณะ

ห้ามใส่ access token, refresh token, app secret, partner key, channel secret,
webhook secret, GPG PIN หรือ passphrase ในข้อความลูกค้า, screenshot, issue,
PR หรือไฟล์ frontend

## English

### 1. Start using the Dashboard

1. Connect the device to the same network as `192.168.74.130`.
2. Open `http://192.168.74.130:18765/`.
3. Use the browser's **Add to Home Screen/Install** option if you want an app-like PWA.
4. Use the **TH/EN** control in the top-right corner to switch language.
5. Refresh when the API status is not online.

The responsive PWA works on Android, iOS, Windows, and desktop browsers. PWA
installation does not grant the browser access to store tokens or secrets.

### 2. Main navigation

- **Overview:** product, conversation, order, review, and channel status counts
- **Unified Inbox:** inspect conversations, send local Autobot tests, and toggle takeover
- **Product Memory:** aliases, ingredients, prices, promotions, and source listings
- **Orders:** create draft orders, receive payment evidence, and review status
- **Skills / Agents:** server-reported capabilities and operating scope
- **n8n Automations:** workflows that remain behind account/webhook verification
- **Channels:** truthful connection status, TH/EN API onboarding guides, and approval workbooks
- **Sales Assets:** local media, selling points, intents, and closing CTAs
- **Settings:** store profile, language, Autobot tone, takeover timeout, and notifications

### 3. Use the inbox and close a sale

1. Open **Unified Inbox** and choose an existing conversation or enter a Customer ID.
2. Send a product, ingredient, price, delivery, or purchase question.
3. The Autobot uses product memory and validated local response assets.
4. When a customer wants to buy, confirm the quantity before creating a draft order.
5. Enable **Human takeover** when a customer asks for a person; automated replies pause.
6. After a payment slip arrives, an authorized reviewer checks it in **Orders**.

The copy is warm, friendly, cute, purchase-oriented, and CTA-led. It never invents
price, stock, shipping, medical outcomes, or payment approval.

### 4. Sales Assets

The **Sales Assets** view shows:

- only local product media from `assets/`
- Thai/English selling points
- intents such as price, ingredients, buy, payment, address, and objections
- closing CTAs appropriate to the product status
- `reference_only` products and products without a verified price

If an image is missing, check the server and `/assets/...`. Do not replace local
asset paths with an external URL without reviewing the asset policy.

### 5. Orders and payment review

- Products without a confirmed price cannot be selected for an order.
- New orders start at `awaiting_payment`.
- Payment evidence moves an order to `pending_review`.
- Only an authorized reviewer can move it to `confirmed`.
- A confirmed order creates a LINE notification outbox event.
- The worker claims events with a lease, retries transport failures, and delivers only after server-side LINE configuration.
- Actual LINE delivery never runs from the browser.

### 6. Channel status

- `Unconfigured`: required server-side values are absent.
- `Configured`: required environment values exist; this is not proof that the API works.
- `Degraded`: a service failed a health/model check.
- `Verified`: provider tests and server verification provide evidence.
- `Outbox`: an event is waiting for delivery.

Facebook, TikTok Shop, Shopee, LINE, n8n, and Gemini are not enabled automatically
in this release. Opening the Dashboard does not authorize any account.

### 7. Basic troubleshooting

| Symptom | Check |
| --- | --- |
| API offline | Check the service, refresh, and call `/api/health`. |
| Product image missing | Check the local `assets/` file and `/assets/` route. |
| Wrong language | Switch TH/EN and check `default_language` in Settings. |
| Bot does not reply | Check Autobot enabled and human takeover state. |
| Cannot create an order | Check price, stock, and product availability. |
| LINE is not delivered | Review Channels, the notification outbox, and `uperfect-worker.service`; never put the token in the browser. |

### 8. Never publish

Never put access tokens, refresh tokens, app secrets, partner keys, channel
secrets, webhook secrets, GPG PINs, or passphrases in customer messages,
screenshots, issues, pull requests, or frontend files.
