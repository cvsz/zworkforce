# Architecture Decision Records (ADR) — AUSI Consolidation

**Baseline Date:** 2026-11-05 UTC+7  
**Monorepo:** `cvsz/zworkforce`  
**Governing Standard:** IEEE 1471 / ISO 42010 Architecture Decisions  

---

## ADR-001: Retention of Separate Bounded FastAPI Sidecars vs Central Consolidation

### Context
การตรวจสอบเบื้องต้นพบ FastAPI services 3 ชุดใน repository (`zworkforce/`, `packages/ztrader/zeaz-intelligence/`, `packages/zider/server/`) ทำให้เกิดข้อสงสัยว่าเป็นการสร้างโค้ดซ้ำหรือไม่

### Decision
**ปฏิเสธการยุบรวม (Do Not Consolidate) ทั้ง 3 ชุดเข้าด้วยกัน**
- `zworkforce/` ทำหน้าที่เป็น Core Orchestration & Control Plane
- `ztrader/zeaz-intelligence/` ทำหน้าที่เป็น Quantitative Financial Scoring & Paper Trading Sidecar
- `zider/server/` ทำหน้าที่เป็น Browser Companion BFF & Playwright Automation Agent
ทั้ง 3 มี Data Model, Dependencies, และ Security Boundary ที่แยกจากกันโดยสิ้นเชิง การคงเป็น Bounded Services แยกกันช่วยรักษา Domain Isolation และป้องกัน Dependency Bloat

---

## ADR-002: Canonical Authority of `packages/zarvis/` Over `services/` Mirrors

### Context
พบโมดูล Z.A.R.V.I.S. ซ้ำซ้อนระหว่าง `packages/zarvis/services/` และ `services/zarvis-*` โดยตรวจพบ Code Drift ซึ่ง `packages/zarvis/` มีฟีเจอร์ใหม่กว่า (เช่น `live_voice.mjs`, `skill-catalog.mjs`)

### Decision
กำหนดให้ **`packages/zarvis/` เป็น Canonical Source of Truth** แต่เพียงผู้เดียว
- การพัฒนาและทดสอบทั้งหมดต้องทำใน `packages/zarvis/`
- โฟลเดอร์ `services/zarvis-*` มีสถานะเป็น Deployment Mirrors ที่จะถูก sync โค้ดผ่าน automated PR หรือ build pipeline
- ห้ามลบ `services/` ทิ้งทันทีเพื่อป้องกัน Docker Compose และ CI workflows แตก

---

## ADR-003: Database-Enforced Idempotency for Durable Billing Ledger

### Context
Issue #346 ระบุถึงความเสี่ยงของการหักเครดิตซ้ำซ้อนและการสูญหายของ State เมื่อ Service รีสตาร์ทใน `services/billing-ledger`

### Decision
เปลี่ยนจาก In-Memory Balance มาใช้ **PostgreSQL Durable Store** (`postgres-store.mjs`) ร่วมกับ Migration `001_durable_billing_ledger.sql`
- บังคับใช้ `idempotency_key UNIQUE` constraint ในระดับฐานข้อมูล
- เมื่อตรวจพบ Key ซ้ำ ให้คืนค่า transaction เดิมทันทีโดยไม่ประมวลผลซ้ำ (HTTP 200/409 idempotent handling)
- บังคับ Fail-Closed ใน production environment เมื่อไม่ได้กำหนด DSN ของ PostgreSQL

---

## ADR-004: Tenant-Isolated Secret & Session Key Pools

### Context
Issue #398 และ #375 พบความเสี่ยงที่การนับ Rate Limit และการ Push ข้อมูลผ่าน SSE จะปะปนข้าม Tenant (Cross-tenant Data Leakage)

### Decision
- **AI Gateway (#398):** บังคับ prefix Redis keys ด้วย `ratelimit:{tenantId}:{key}` พร้อมส่ง header `X-RateLimit-Tenant`
- **zTrader Intelligence (#375):** ปรับปรุง `EventBus` ให้แยก `_subscribers_by_tenant` และปรับ `AnalysisStore` ให้มีคอลัมน์ `tenant_id` ในทุกตาราง
- **Zider BFF (#397):** แยกที่จัดเก็บไฟล์ PDF ตาม sub-directory ของ Tenant ID

---

## ADR-005: Strict Removal of Cloudflare PostgreSQL Ingress Exposure

### Context
Issue #385 และ #399 พบการประกาศ Route `/postgres` ไปยังพอร์ต `127.0.0.1:5432` ภายใน Cloudflare Tunnel Ingress

### Decision
**ถอดถอน Route และ Ingress ทั้งหมดที่เกี่ยวกับฐานข้อมูลออกจาก Cloudflare Tunnel ทันที**
- ห้าม Expose PostgreSQL Port สู่ Public Network
- การเชื่อมต่อฐานข้อมูลต้องกระทำผ่าน Private VPC, WireGuard Overlay, หรือ Internal Supabase Session Pooler ภายใต้ Server-Side Credential Boundary เท่านั้น
