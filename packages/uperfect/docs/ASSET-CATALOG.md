# Product and Chatbot Asset Catalog / คลังสินค้าและ asset แชท

## ภาษาไทย

`assets/chatbot/asset-manifest.json` เป็นบัญชี media local และ
`assets/chatbot/sales_response_assets.json` เป็นข้อความ TH/EN ของ Autobot

### Canonical asset directories

- `assets/loe_vit_c_aura_serum/` เป็น directory เดียวของ media Loe VIT C ทั้งหมด
  โดยแยก technical dossier กับ `Loe_Vit_C_Aura_Serum_Promo_TH.md` และ
  `Loe_Vit_C_Aura_Serum_Promo_EN.md` ตาม source ที่มีอยู่
- `assets/loe_soap/` เก็บภาพอ้างอิงและเอกสาร TH/EN ของ `LOE_CHARCOAL_SOAP`
- `assets/suea_rong_hai_mala_chili_oil/` เก็บภาพและเอกสาร TH/EN ของ
  `MALA_CHILI_OIL`
- `assets/choe/` และ `assets/the_copper/` เก็บ media อ้างอิงของสินค้าที่เหลือ

ทุก path ใน manifest ต้องชี้ไปยังไฟล์ local ที่มีอยู่จริงและต้องไม่ใช้ชื่อ
โฟลเดอร์เดิมที่เป็นชื่อภาษาไทยหรือ path ที่มีช่องว่างเปล่า

### สินค้าหลัก

| Product ID | สถานะ | ราคา | การปิดการขาย |
| --- | --- | --- | --- |
| `LOE_VITC_SERUM` | active, catalog review | 98 THB ใน brief; verify ก่อน live | เสนอโปร/สร้าง draft หลังยืนยันจำนวน |
| `MALA_CHILI_OIL` | active, admin review | ไม่ได้ระบุ | ตรวจราคา/สต็อกโดยแอดมินก่อนเสนอ total |
| `LOE_CHARCOAL_SOAP` | reference only | ไม่ได้ยืนยัน | ตรวจราคา/สต็อกโดยแอดมินก่อนเสนอ |
| `CHOE_FOUNDATION` | reference only | ไม่ได้ยืนยัน | ส่งต่อให้แอดมินตรวจ |
| `THE_COPPER_CREAM` | reference only | ไม่ได้ยืนยัน | ส่งต่อให้แอดมินตรวจ |

### Policy

- media ต้องเป็น local relative path ใต้ project root
- ห้ามใช้ CAPTCHA หรืออ้างว่า export สำเร็จเมื่อ public retrieval ถูกบล็อก
- ทุก intent และ CTA ต้องมี TH/EN
- sensitive skin ต้องมี patch-test และหยุดใช้เมื่อระคายเคือง
- unpriced product ห้ามสร้าง order

## English

`asset-manifest.json` indexes local media. `sales_response_assets.json` contains
the bilingual Autobot intents, objections, selling points, and closing CTAs.

### Canonical asset directories

- `assets/loe_vit_c_aura_serum/` is the single canonical directory for all Loe
  VIT C source media. The shorter source dossier is named
  `Loe_Vit_C_Aura_Serum_Promo_TH.md` / `..._EN.md`.
- `assets/loe_soap/` contains the TH/EN reference documents and image for
  `LOE_CHARCOAL_SOAP`.
- `assets/suea_rong_hai_mala_chili_oil/` contains the TH/EN documents and
  images for `MALA_CHILI_OIL`.
- `assets/choe/` and `assets/the_copper/` contain reference media for the other
  products.

Every manifest path must resolve to an existing local file. The manifest must
not use the former Thai directory name or a blank-space directory.

| Product ID | State | Price | Closing behavior |
| --- | --- | --- | --- |
| `LOE_VITC_SERUM` | active, catalog review | 98 THB in brief; verify before live | offer/draft after quantity confirmation |
| `MALA_CHILI_OIL` | active, admin review | not supplied | admin verifies price/stock before total |
| `LOE_CHARCOAL_SOAP` | reference only | unverified | admin verifies price/stock before offer |
| `CHOE_FOUNDATION` | reference only | unverified | admin review |
| `THE_COPPER_CREAM` | reference only | unverified | admin review |

Media must be local and validated. A CAPTCHA-blocked public retrieval is never
reported as a successful export. Every response asset has TH/EN content. Unpriced
products cannot create orders, and sensitive-skin replies include patch-test and
stop-use guidance.
