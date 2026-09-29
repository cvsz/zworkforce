# ZEAZ Center Control Plane

## วัตถุประสงค์

เอกสารนี้กำหนด contract สำหรับการประสานงานระดับ repository ในระบบ ZEAZ โดยตั้งใจให้ zWorkforce แสดงข้อมูลสำหรับ operator เกี่ยวกับ GitHub repositories, Cloudflare edge resources, release evidence และพื้นฐานโครงการที่สร้างจาก template

ปัจจุบันมีเฉพาะ Phase 0 ได้แก่ contract, schema และตัวอย่าง inventory เท่านั้น ยังไม่มี dashboard inventory, GitHub mutation, Cloudflare route management หรือ generator ที่เชื่อมต่อระบบภายนอก เอกสารนี้จึงไม่ได้ยืนยันว่าความสามารถเหล่านั้นถูก implement หรือ provision แล้ว

## ขอบเขตของ control plane

การรวมข้อมูลจากหลาย repository ไม่เปลี่ยนเจ้าของทรัพยากร:

- source ของแอปพลิเคชันยังเป็นของ repository แอปพลิเคชันนั้น
- จะเปลี่ยน Cloudflare resource ผ่าน zWorkforce ได้เฉพาะเมื่อ Terraform หรือ declaration ที่ repository เป็นเจ้าของระบุ edge ownership ไว้อย่างชัดเจน
- การมี hostname ใน zone `zeaz.dev` ไม่ได้ให้สิทธิ์ mutation แก่ zWorkforce โดยอัตโนมัติ
- การจัดการ GitHub repository ต้องมี permission ของ repository เป้าหมายอย่างชัดเจน
- production deployment, DNS/Tunnel apply, secret rotation, การเปลี่ยน infrastructure แบบทำลายข้อมูล และ release promotion ต้องผ่าน approval

schema ของ inventory อยู่ที่ [`schemas/center-control-plane.schema.json`](../schemas/center-control-plane.schema.json) และตัวอย่างที่ไม่มี secret อยู่ที่ [`examples/center-control-plane.example.json`](../examples/center-control-plane.example.json)

## หน้า operator

พื้นฐานหน้า browser อยู่ที่ [`apps/agent-control-panel`](../apps/agent-control-panel/)

โครงสร้างการนำทางที่วางแผนไว้:

```text
ZEAZ CENTER CONTROL PLANE
├── ภาพรวม
├── Repositories
│   ├── ทั้งหมด
│   ├── Production
│   ├── ต้องอัปเดต
│   └── เก็บถาวร
├── Generator
│   ├── สร้าง Repository
│   ├── Profiles
│   └── Templates
├── GitHub
│   ├── Pull Requests
│   ├── Actions / CI
│   ├── Security
│   ├── สถานะ Branch / Ruleset
│   └── Releases
├── Cloudflare
│   ├── Hostnames
│   ├── Ownership
│   ├── Tunnel / Origin Mapping
│   ├── สถานะ Access Policy
│   └── หลักฐาน Terraform Plan
├── Production
│   ├── Readiness Gates
│   ├── Deployments
│   ├── Rollback
│   ├── Backup / Restore
│   └── DR
├── AI Workforce
│   ├── Agents
│   ├── Skills
│   ├── Tasks
│   └── Automations
└── Audit Log
```

โค้ดใน browser เป็นหน้าแสดงผลและอนุมัติสำหรับ operator ไม่ใช่ client ที่มีสิทธิ์เรียก infrastructure โดยตรง Provider credentials, GitHub installation secrets, Cloudflare API tokens, database credentials และ signing material ต้องอยู่ฝั่ง server

## Repository generator

Generator ในอนาคตจะใช้ project profile ที่ผ่าน approval และแหล่ง repository foundation เช่น `cvsz/ztemplate`

คำขอสร้างโครงการควรระบุ:

- owner, ชื่อ repository, visibility, description และ license
- profile เช่น minimal, API, web, full-stack, SaaS, worker, agent หรือ platform
- runtime, framework และ package manager
- database, cache และ queue
- ตัวเลือก dashboard
- ข้อกำหนด Docker, Kubernetes และ Cloudflare
- CI/security baseline
- CODEOWNERS และ support policy
- observability และ recovery expectations

การสร้างแบ่งเป็นสองช่วง:

1. **Preview** — แสดงไฟล์และการตั้งค่าที่จะสร้างโดยยังไม่เปลี่ยนระบบ
2. **Apply** — สร้าง repository, branch หรือไฟล์หลังผ่าน authorization แล้ว

การสร้าง repository เป็นเพียงการตั้งพื้นฐาน ไม่ได้ยืนยัน production readiness ของแอปพลิเคชัน

## การใช้ zTemplate

`cvsz/ztemplate` เป็นแหล่ง repository foundation สำหรับ repository ใหม่และการ sync baseline อย่างปลอดภัย

การ sync กับ repository ที่มีอยู่ต้องตรวจสอบก่อนและใช้การเปลี่ยนแปลงแบบจำกัดขอบเขต:

```text
inventory -> compatibility review -> focused branch -> minimal diff
          -> exact-head CI/security checks -> review -> merge
```

ห้ามเขียนทับกฎ AGENTS, CI matrices, deployment workflows, infrastructure ownership หรือ security contacts เฉพาะโครงการ

## มุมมอง Cloudflare

Control plane อาจอ่าน inventory ของ hostnames ใน `zeaz.dev` ได้ในอนาคต แต่สิทธิ์ mutation ต้องมาจาก declaration ของ ownership

แต่ละ hostname ที่จัดการควรระบุ:

- hostname ซึ่งเป็น key แบบ lowercase และไม่ซ้ำ
- application repository และ edge owner repository
- environment และ intended origin
- tunnel identifier/reference ที่ไม่มี secret
- ข้อกำหนด Access
- path ของไฟล์ Terraform และ resource address ที่เฉพาะเจาะจง
- desired/effective state
- structured evidence ล่าสุดที่ใช้ยืนยันสถานะ

### กฎสำหรับ Cloudflare mutation

จะดำเนินการ Cloudflare action ได้เมื่อครบทุกข้อ:

1. ระบุ edge owner ของ hostname เป้าหมายอย่างชัดเจน
2. การเปลี่ยนแปลงอยู่ใน configuration ของ repository เจ้าของ
3. มี preview/plan ให้ตรวจสอบ
4. ไม่มี destroy/change ที่ไม่เกี่ยวข้อง หรือได้รับ approval อย่างชัดเจนแล้ว
5. operator อนุมัติ plan/digest ที่แน่นอน
6. บันทึกผล post-apply verification แล้ว

การอ่าน inventory อย่างเดียวไม่ต้องใช้สิทธิ์ mutation

## มุมมอง GitHub fleet

เมื่อพัฒนาแล้ว แต่ละ repository ควรแสดงข้อมูลต่อไปนี้:

- SHA ของ default branch ที่ตรวจสอบ
- จำนวน PR/issue ที่เปิดอยู่
- ผลของ required checks
- สถานะ CodeQL, Dependency Review และ Dependabot
- สถานะ branch/ruleset เมื่ออ่านได้
- เวอร์ชัน baseline และ drift ของ repository foundation
- release ล่าสุดและ deployment evidence
- สถานะ readiness แยกตาม gate ที่เกี่ยวข้อง

การยืนยันตัวตนสำหรับ automation หลาย repository ควรใช้ GitHub App installation แบบ least privilege แทน personal token ที่มีสิทธิ์กว้าง

## สถานะและหลักฐาน

แต่ละ gate ใช้สถานะต่อไปนี้:

- `VERIFIED`
- `PARTIALLY VERIFIED`
- `UNVERIFIED`
- `BLOCKED`
- `NOT APPLICABLE`

การแสดงผล `VERIFIED` ต้องมี structured evidence ซึ่งระบุ revision ที่ตรวจสอบ, environment, เวลา, command หรือ run, ผลลัพธ์ และ durable artifact reference สถานะ `VERIFIED` ที่ไม่มีหลักฐานต้องไม่ผ่าน schema

ห้ามสรุปว่า production ready หากมี gate ที่เกี่ยวข้องเป็น `PARTIALLY VERIFIED`, `UNVERIFIED` หรือ `BLOCKED`

Repository เก็บสถานะไว้แยกตาม stable gate ID ไม่ใช้ค่า readiness รวมค่าเดียว เพื่อให้ operator เห็น gate ที่ยังขวาง readiness ได้

## ขั้นตอน mutation

การเปลี่ยนแปลงที่มีผลกระทบสูงต้องใช้ proposal/approval/execution flow:

```text
read current state
  -> generate preview / diff / plan
  -> policy evaluation
  -> immutable action digest
  -> explicit approval
  -> compare-and-set execution
  -> verification
  -> durable audit evidence
```

ตัวอย่างงานที่ต้อง approval:

- สร้างหรือเปลี่ยน public Cloudflare DNS/Tunnel/Access state
- apply Terraform
- production deployment
- เปลี่ยน repository security/ruleset
- credential rotation
- เผยแพร่ release/tag
- ลบ branch หรือ resource แบบทำลายข้อมูล

## แนวทางพัฒนา Dashboard

Control panel ใช้ Next.js/React และควรแยก data model ออกจาก visual theme

อาจใช้ AdminLTE เป็น visual/design adapter เสริมได้ แต่ห้ามทำให้เป็น runtime dependency ที่จำเป็นต่อ control-plane API หรือ repository generator การพัฒนาต้องรักษา Next.js routing, server-side secret boundaries, accessibility, responsive behavior และ testability

## ระยะการส่งมอบ

### Phase 0 — contract และ inventory

- schema สำหรับ center-control registry
- ขอบเขต ownership และ mutation
- information architecture ของ dashboard
- contract ของ generator

ระยะนี้มี contract, schema และตัวอย่างเป็นผลส่งมอบ ยังไม่ใช่ runtime inventory

### Phase 1 — read-only fleet dashboard

- GitHub repository inventory
- Cloudflare ownership/desired-state inventory
- สรุป CI/security/readiness
- ไม่มี production mutation

### Phase 2 — repository generator

- zTemplate profiles
- preview ของ file tree และ settings
- ขั้นตอนสร้าง repository แบบมีขอบเขต
- audit record ที่ตรวจย้อนกลับได้

### Phase 3 — GitHub mutations ที่ผ่าน approval

- proposal สำหรับ branch/ruleset/security settings
- สร้าง pull request และ sync baseline อย่างปลอดภัย
- ห้าม force merge หรือ bypass checks

### Phase 4 — Cloudflare mutations ที่ผ่าน approval

- preview การเปลี่ยนแปลงจาก Terraform
- approval ที่ผูกกับ exact plan
- apply ผ่าน repository เจ้าของ
- ตรวจ DNS/TLS/origin หลัง apply

### Phase 5 — production operations แบบผสาน

- deployment/release/recovery evidence
- alerting และ incident context
- rollback/restore controls แยกตาม environment

แต่ละระยะต้องมี implementation และ evidence ของตัวเองก่อนทำเครื่องหมายว่าเสร็จ
