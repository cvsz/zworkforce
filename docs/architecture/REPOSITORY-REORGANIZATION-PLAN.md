# ZWorkforce Repository Reorganization Plan

**Version:** 1.0 (Audit & Planning Baseline)  
**Date:** 2026-11-05 UTC+7  
**Authority:** `docs/MASTER-PROMPT-031126.md` Section 5 & 6  
**Status:** Approved Architecture Plan / Safe Staged Execution  

---

## 1. Executive Summary & Principles

การปรับปรุงโครงสร้าง (Reorganization) ของ monorepo `cvsz/zworkforce` ขนาด 3,092 ไฟล์ ต้องยึดหลักการทางวิศวกรรมที่เคร่งครัดตาม `AGENTS.md` และ MASTER-PROMPT Part 2:
1. **Never blindly delete duplicate files**: ห้ามลบไฟล์ซ้ำโดยไม่ตรวจ code drift, consumer, หรือ deployment target
2. **Preserve working contracts & imports**: ไม่ทำลาย public API contracts หรือ import paths ที่กำลังทำงาน
3. **Canonical Source Identification**: กำหนดให้ `packages/zarvis/` เป็น Single Source of Truth สำหรับ Z.A.R.V.I.S. modules
4. **Gradual Migration**: การย้ายไฟล์ต้องทำเป็น PR ย่อยที่มี automated tests รองรับและมี rollback plan ชัดเจน

---

## 2. Reorganization Strategy by Module Category

### 2.1 Core Python Control Plane (`zworkforce/`)
- **สถานะ:** Canonical อยู่แล้ว (137 ไฟล์)
- **การจัดระเบียบ:** คงไว้ที่รูทของ repository เนื่องจาก CLI, pyproject.toml, Dockerfile และ CI tests ผูกกับ import `zworkforce.*`

### 2.2 Z.A.R.V.I.S. Stack (`packages/zarvis/` vs `services/zarvis-*` & `apps/zarvis-*`)
- **การวิเคราะห์:** 
  - `packages/zarvis/services/zarvis-orchestrator/` และ `zarvis-task-gateway/` มีฟีเจอร์นำหน้า `services/`
  - `services/zarvis-*` และ `apps/zarvis-*` ยังถูกอ้างอิงใน `compose.yaml` และ workflows
- **แผนงาน:**
  - **Phase 1 (ปัจจุบัน):** กำหนด canonical ownership ใน `MODULE-OWNERSHIP.md` และห้ามแก้ไขที่ `services/` โดยตรง
  - **Phase 2 (Next PR):** Sync code drift จาก `packages/zarvis/services/` ไปยัง `services/` เพื่อให้อิมเมจ production ได้รับฟีเจอร์ล่าสุด
  - **Phase 3 (Long-term):** อัปเดต Dockerfile/Compose ให้ build จาก `packages/zarvis/` โดยตรง แล้วค่อย deprecate `services/zarvis-*`

### 2.3 Dead & Scratch Files Cleanup
- **ไฟล์เป้าหมาย:**
  - `packages/zeto/test.txt`
  - `packages/zeto/test_out.txt`
  - `packages/zeto/test/operatorApi.integration.test.js.bak`
  - `packages/zeto/test/operatorRuntime.integration.test.js.bak`
- **แผนงาน:** ลบออกใน PR cleanup เฉพาะจุด (ไม่กระทบ build หรือ test)

### 2.4 Browser Companion & Sidecars
- `packages/zider/` และ `packages/ztrader/zeaz-intelligence/` คงอยู่ใน `packages/` ตามรูปแบบ monorepo library/service package

---

## 3. Rollback & Safety Gates

ทุกขั้นตอนของการเคลื่อนย้ายไฟล์ต้องผ่าน:
```bash
python3 -m compileall -q zworkforce tests scripts
PYTHONPATH=.:tests python3 -m unittest discover -s tests -v
git diff --check
```
หากมี test discovery ใดหายไป หรือ import ล้มเหลว ให้ revert ทันที
