# Master Trading 24/7 — zTrader Intelligence

เอกสารนี้กำหนดขอบเขตการพัฒนาระบบ Trading ของแพ็กเกจ `zeaz-intelligence` โดยใช้ **Paper Trading เท่านั้น** การมี API หรือ ledger ในแพ็กเกจนี้ไม่ได้หมายความว่าระบบพร้อมเทรดเงินจริงหรือเชื่อมต่อ exchange

## 1. ขอบเขตและข้อห้าม

- โหมดที่รองรับในงานนี้คือ `paper` เท่านั้น
- ไม่มีการส่งคำสั่งไป exchange, broker หรือ blockchain
- ไม่มีการเก็บ private key, seed phrase หรือ exchange trading credentials
- ห้ามเปิดใช้ live execution และต้องรักษา `live_execution_enabled: false`
- การวิเคราะห์หรือ Trade Plan เป็นเพียง decision support ไม่ใช่คำสั่งซื้อขายอัตโนมัติ
- ทุก endpoint ของ Paper Trading ต้องรับ `X-Tenant-ID` และตรวจ scope ของบัญชี
- การส่งคำสั่งซ้ำด้วย idempotency key เดิมและ payload เดิมต้องไม่สร้าง fill ซ้ำ
- หาก key เดิมถูกใช้กับ payload ต่างกัน ต้องปฏิเสธคำขอ
- การเปลี่ยนแปลงยอดเงิน, position และ order ต้องอยู่ใน SQLite transaction เดียวกัน

## 2. สถาปัตยกรรม

```text
Market / Intelligence Input
        |
        v
Scoring + Trade Plan (decision support)
        |
        v
Paper Order API
        |
        v
Deterministic Validation
  - tenant/account scope
  - cash and holdings
  - quantity and price
  - fee and slippage
  - idempotency
        |
        v
SQLite Transaction
  - paper_orders
  - paper_positions
  - paper_accounts
        |
        v
Account Summary / Order History
```

Paper broker คำนวณ fill จาก `reference_price` ที่ caller ส่งมา โดยเพิ่ม slippage สำหรับ BUY และลด slippage สำหรับ SELL ค่าดังกล่าวเป็นสมมติฐานเพื่อการจำลอง ไม่ใช่ quote ที่ยืนยันจากตลาด

## 3. API

ทุก request ต้องส่ง header `X-Tenant-ID` ให้ตรงกับ tenant ที่สร้างบัญชี

### สร้างบัญชีจำลอง

```bash
curl -X POST http://127.0.0.1:8218/v1/paper/accounts \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo-tenant' \
  -d '{"initial_cash_usd": 10000}'
```

เก็บ `account_id` จาก response ไว้ใช้กับคำขอถัดไป

### ส่งคำสั่งจำลอง

```bash
curl -X POST http://127.0.0.1:8218/v1/paper/orders \
  -H 'Content-Type: application/json' \
  -H 'X-Tenant-ID: demo-tenant' \
  -d '{
    "account_id": "REPLACE_WITH_ACCOUNT_ID",
    "symbol": "DEMO",
    "chain": "solana",
    "side": "buy",
    "quantity": 2,
    "reference_price": 10,
    "fee_bps": 10,
    "slippage_bps": 5,
    "idempotency_key": "demo-buy-order-0001"
  }'
```

ค่าธรรมเนียมและ slippage ระบุเป็น basis points (bps); 100 bps เท่ากับ 1%. `idempotency_key` ต้องไม่ซ้ำสำหรับแต่ละ order ภายในบัญชี

### ดูบัญชีและประวัติ

- `GET /v1/paper/accounts/{account_id}`
- `GET /v1/paper/accounts/{account_id}/orders?limit=100`

ทั้งสอง endpoint ต้องส่ง `X-Tenant-ID` เหมือนตอนสร้างบัญชี

## 4. บัญชีและการคำนวณ

- BUY: หัก `quantity × fill_price + fee` จาก cash
- SELL: เพิ่ม `quantity × fill_price - fee` เข้า cash
- Average cost รวมค่า fee ของการซื้อ
- Realized PnL เมื่อขายคำนวณจาก net sale proceeds หัก average cost ของจำนวนที่ขาย
- Unrealized PnL ใช้ mark price จาก fill ล่าสุดของสินทรัพย์นั้น
- Equity = cash + market value ของ positions
- บัญชีและประวัติ order อยู่ใน SQLite และยังคงอยู่หลัง restart

ข้อจำกัด: เป็นโมเดล fill แบบเต็มจำนวน (full fill) ไม่มี partial fill, order book depth, market impact, gas หรือ chain-specific transaction failure ในเวอร์ชันนี้ ผลลัพธ์จึงเป็นการจำลอง ไม่ใช่การคาดการณ์ผลการซื้อขายจริง

## 5. การตรวจสอบและ tests

รันจากโฟลเดอร์แพ็กเกจ:

```bash
make lint
make test
```

ชุดทดสอบควรครอบคลุม:
- cash เริ่มต้น, BUY/SELL และค่าธรรมเนียม
- slippage และ average cost
- cash ไม่พอและขายเกิน holdings
- idempotency และ payload mismatch
- persistence หลังสร้าง store ใหม่
- tenant scope และ API headers
- Trade Plan ที่มี support/price geometry ผิดปกติ
- direction และจำนวนเงิน wallet flow ที่ไม่ถูกต้อง

## 6. ข้อกำหนดก่อนขยายระบบ

ก่อนใช้กับข้อมูลหรือ workflow ที่มีความสำคัญมากขึ้น ต้องเพิ่มหรือยืนยัน:
- authentication ที่เชื่อถือได้และ authorization ผูกกับ identity ของ tenant (header เพียงอย่างเดียวไม่ใช่ authentication)
- migration strategy สำหรับฐานข้อมูลที่มีอยู่
- daily loss / max drawdown / per-market และ aggregate exposure limits
- stale-price checks และแหล่งราคาที่ตรวจสอบได้
- reconciliation, backup/restore และ audit retention
- การทดสอบ concurrency ภายใต้โหลดจริง
- การทบทวน security และการตรวจสอบผลลัพธ์บน environment แยก

**สถานะ:** Paper Trading implementation candidate. ไม่ใช่ live-trading implementation และไม่ถือว่า production-ready จากการมี unit tests เพียงอย่างเดียว.
