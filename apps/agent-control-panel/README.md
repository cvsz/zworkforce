# zWorkforce Agent Control Panel

หน้า operator ที่พัฒนาด้วย Next.js/React สำหรับ ZEAZ Center Control Plane

Browser ใช้สำหรับแสดงข้อมูลและอนุมัติเท่านั้น ห้ามส่ง GitHub App private keys, Cloudflare API tokens, provider credentials, database passwords หรือ server-side secrets อื่นมายัง browser

ดูรายละเอียด contract ได้ที่ [ZEAZ Center Control Plane](../../docs/CENTER-CONTROL-PLANE.md)

## หน้าสำหรับ operator ในแผนงาน

- ภาพรวม SLO, queue และสถานะ workforce
- inventory ของ repository
- repository generator
- GitHub pull requests, Actions, security และ releases
- ownership ของ Cloudflare hostname และ desired/effective state
- หลักฐาน production readiness
- AI agents, skills และ automations
- durable audit log

Control ที่เปลี่ยนแปลงระบบต้องใช้ contract แบบ proposal/approval/execution หน้า UI ห้ามเรียก provider API ที่มี privileged access โดยตรง

## Theme ของ Dashboard

แอปยังใช้ Next.js/React ต่อไป

อาจเพิ่ม AdminLTE เป็น visual/design adapter เสริมได้ แต่ไม่ใช่ dependency บังคับของ control plane การปรับ theme ต้องรักษาสิ่งต่อไปนี้:

- Next.js routing และ server/client boundaries
- keyboard/focus behavior ที่เข้าถึงได้
- responsive layout
- auth/RBAC boundaries ที่มีอยู่
- loading/error/empty states ที่ทดสอบได้
- ไม่มี configuration ที่บรรจุ secret ใน browser

## พัฒนาในเครื่อง

ใช้ package manager ของ repository:

```bash
pnpm --filter agent-control-panel dev
pnpm --filter agent-control-panel lint
pnpm --filter agent-control-panel build
```

การรัน UI ในเครื่องไม่ได้ยืนยันว่ามีการตั้งค่า GitHub, Cloudflare, deployment หรือ production mutation permissions แล้ว
