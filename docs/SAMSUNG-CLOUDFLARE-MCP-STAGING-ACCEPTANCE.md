# Samsung + Cloudflare MCP — Staging Acceptance

เอกสารนี้ใช้สำหรับ Operator ทดสอบ MCP บน Staging เท่านั้น การ Merge PR, Unit Test ผ่าน หรือ Environment Variable ถูกตั้งค่า **ไม่ใช่** หลักฐาน Production Readiness

## Prerequisites

- ระบุ Revision SHA ของ `main`, Environment, Operator และเวลา UTC ก่อนเริ่ม
- ตรวจสอบ Role/Scope ของ MCP Principal และแยก Tenant ทดสอบอย่างน้อยสอง Tenant
- ห้ามใส่ Token, Private Key, Credentials หรือ Raw API Response ลงใน Evidence
- ตรวจ Cloudflare Zone/Account Ownership จาก Manifest ที่ได้รับอนุมัติ ห้ามอนุมานสิทธิ์จาก Hostname หรือ Token
- ทดสอบ Samsung บนเครื่องที่ได้รับอนุญาตและมี SDK/Signing Profile ถูกต้องเท่านั้น

## Automated Repository Checks

```bash
git checkout main
git pull --ff-only origin main
python3 -m compileall -q zworkforce tests
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_live_mcp.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_pagination_mcp.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_read_errors_mcp.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_audit_mcp.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_samsung_sdk_probe_mcp.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_samsung_builder_preflight_mcp.py' -v
```

## Cloudflare Acceptance

1. ตั้งค่า `ZWORKFORCE_CLOUDFLARE_READ_TENANTS` และ Token ผ่าน Secret Manager เฉพาะ Staging
2. ทดสอบ `cloudflare.live_inventory` กับ Zone ใน Allowlist แล้วตรวจ `GET /zones/{zone_id}` และค่า `has_more`
3. ใช้ Tenant B เรียก Zone/Account ของ Tenant A ต้องถูกปฏิเสธ โดยไม่มี Provider Request
4. ยืนยันว่าการอ่าน DNS/Tunnel มี Pagination ตาม Provider Contract, 429 ไม่ Retry อัตโนมัติ, 401/403 ไม่เปิดเผย Error Body
5. ตรวจ `app.db.audit` ว่ามี Actor, Tenant, Resource, Outcome และไม่เก็บ Token/Raw Response
6. ทดสอบ Audit Store unavailable ต้อง Fail Closed
7. ตรวจว่ามีเฉพาะ GET Requests และไม่มี DNS/Tunnel Mutation
8. บันทึก Redacted Evidence, Run ID, SHA, เวลา, รายการ Test และผลจริง

## Samsung Acceptance

1. ใช้ `samsung.compatibility` โดยระบุ Model Year ที่ยืนยันจากข้อมูลผู้ผลิต
2. ใช้ `samsung.sdk_environment` ตรวจ Environment โดยไม่แสดง SDK Path หรือ Secret
3. ใช้ `samsung.builder_preflight` และยืนยัน `build_executed=false`, `signing_verified=false`, `ready_to_build=false`
4. ตรวจ Samsung Legacy UA40F5500AR แยกจาก Tizen; **ห้าม** ใช้ Tizen `.wgt` กับ Legacy Device โดยไม่มีหลักฐานรองรับ
5. รวบรวม Official SDK/Platform Compatibility, License และ Signing Evidence ก่อนอนุมัติ Builder จริง
6. Hardware, Build, Install, USB Compatibility และ URL Full Screen ยังเป็น `UNVERIFIED` จนกว่าจะทดสอบจริงอย่างได้รับอนุญาต

## Evidence Record

| Field | Required |
| --- | --- |
| Repository SHA | Exact tested SHA |
| Environment | staging; ไม่มี Secrets |
| Timestamp | UTC ISO-8601 |
| Operator | Authenticated identity |
| Test or workflow | Command/CI Run URL |
| Cloudflare resources | Redacted allowlisted IDs |
| Samsung target | Approved model/firmware metadata |
| Outcome | VERIFIED / PARTIALLY VERIFIED / UNVERIFIED / BLOCKED |
| Evidence | Durable URI/Run ID |
| Reviewer | Independent approval identity |

**GO:** ผ่าน Security Gates, Exact Revision, Staging Live Verification และมี Evidence ครบทุกข้อที่เกี่ยวข้อง

**NO-GO:** ขาด Token/SDK/Hardware, มี Cross-tenant Leak, ไม่มี Audit, Provider Error ไม่ถูกปกปิด หรือขาด Approval

การเปิด Production ต้องปฏิบัติตาม `AGENTS.md` และ `docs/PRODUCTION-EVIDENCE.md` เพิ่มเติม
