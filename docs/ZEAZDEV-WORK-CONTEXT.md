# บริบทการทำงานของ ZeaZDev และโครงสร้างพื้นฐานโดเมน

## วัตถุประสงค์

เอกสารนี้เป็นบริบทของระบบนิเวศ ZeaZDev สำหรับ agents, operators, developers และ automation workflows ใน zWorkforce โดยอธิบายความสัมพันธ์ระหว่างซอฟต์แวร์ของ ZeaZDev, namespace zeaz.dev, Cloudflare edge infrastructure, Terraform infrastructure-as-code และ zWorkforce

## หลักการด้านวิศวกรรม

> โค้ดเป็นภาระ ยิ่งมีโค้ดและส่วนประกอบน้อย สถาปัตยกรรมยิ่งชัดเจนและระบบยิ่งเชื่อถือได้

แนวทางที่ต้องการคือ secure-by-default, ทำซ้ำได้, สังเกตการณ์ได้, กู้คืนได้, กำหนด infrastructure-as-code, ใช้ local-first หรือ self-hosted เมื่อเหมาะสม และดูแลต่อเนื่องได้ในระยะยาว

## ระบบนิเวศ ZeaZDev

ZeaZDev เป็นระบบนิเวศเทคโนโลยีที่เชื่อมโยง applications, platforms, AI systems, automation, infrastructure และ business products เข้าด้วยกัน

zWorkforce ทำหน้าที่เป็นเครื่องมือด้าน AI/agent/automation และ governed control plane โดยรองรับ durable tasks, workflows, scheduling, events, agents, provider/model routing, policy-as-code, approvals, MCP, memory, artifacts, FinOps, observability และ operational controls

```text
Infrastructure
    ↓
Platform / Control Plane
    ↓
ZWorkforce AI Workforce / Automation
    ↓
Application Services
    ↓
Products / User Interfaces
```

repository นี้เป็น product monorepo ที่มี Python control plane อยู่ใน zworkforce/ และ product implementations อยู่ภายใน apps/, services/ และ packages/ ขอบเขตของแต่ละผลิตภัณฑ์ใน monorepo กำหนดตาม subtree และ AGENTS.md ที่ใกล้ที่สุด ห้ามสรุปว่า implementation ของผลิตภัณฑ์ใน tree นี้ต้องอยู่ใน repository อื่น

## โดเมนหลัก: zeaz.dev

`zeaz.dev` เป็นโดเมนที่หลาย repository และบริการในระบบนิเวศ ZeaZDev ใช้ร่วมกัน `zworkforce` จัดการเฉพาะ Cloudflare resources และ hostname ที่มี Terraform resource ประกาศ ownership ไว้ใน repository นี้เท่านั้น ไม่ได้เป็นเจ้าของทั้ง Cloudflare zone หรือ namespace ตัวอย่างเช่น corporate `www.zeaz.dev` routes ระบุว่าเป็นของ `cvsz/zeaz-platform` ใน `infrastructure/terraform/cloudflare/terraform.tfvars.example`

ก่อนแก้ route ให้ตรวจ Terraform resource, repository owner และสถานะจริงใน Cloudflare สำหรับ hostname นั้นโดยเฉพาะ การอยู่ใน zone เดียวกันหรือการมี credentials เข้าถึง zone ไม่ได้แปลว่า repository นี้เป็นเจ้าของ route นั้น

hostname สำหรับ production ภายใต้ `zeaz.dev` ควรเชื่อมโยงกับบริการ environment, origin, security boundary และ deployment configuration ที่ตั้งใจใช้ได้ รายการด้านล่างเป็นเพียง hostname ตัวอย่างบางส่วนที่ทราบ ไม่ใช่ inventory ที่ครบถ้วนหรือแหล่งอ้างอิงสำหรับการเปลี่ยน infrastructure

### ตัวอย่าง hostname บางส่วน

```text
zeaz.dev

app.zeaz.dev
api.zeaz.dev
admin.zeaz.dev
account.zeaz.dev
auth.zeaz.dev
pay.zeaz.dev
wallet.zeaz.dev

zttato.zeaz.dev
zneon.zeaz.dev
```

inventory ที่เชื่อถือได้ต้องตรวจสอบจาก Terraform และยืนยันเทียบกับสถานะจริงใน Cloudflare ก่อนใช้อ้างอิงหรือทำการเปลี่ยนแปลง

## สถาปัตยกรรม Cloudflare และ Terraform

```text
Internet
    │
    ▼
Cloudflare
    ├── DNS / Proxy / SSL/TLS / WAF / Access
    └── Routing
        ├── Worker routes (for example, www.zeaz.dev)
        │     └── Cloudflare Workers ── D1 when configured
        │
        └── Origin routes
              └── Cloudflare Tunnel when configured
                    └── Origin Infrastructure
                          ├── Docker
                          ├── Kubernetes / k3s where justified
                          ├── Internal services
                          ├── Web applications
                          └── AI / automation services
```

เมื่อใช้ Cloudflare Tunnel ควรรักษา origin ให้เป็น private เท่าที่ทำได้ แทนการเปิด inbound ports โดยไม่จำเป็น

แนวทางที่ตั้งใจใช้คือให้ Terraform อธิบาย desired state ของ Cloudflare infrastructure ให้ Cloudflare ทำหน้าที่เป็น edge/execution layer และใช้ Git เก็บประวัติ การ review และ traceability การเปลี่ยนแปลงจาก Cloudflare dashboard ต้องไม่กลายเป็น permanent source of truth โดยไม่มีการบันทึกและตรวจสอบใน repository

## วงจรการเปลี่ยนแปลง Terraform

การเปลี่ยน infrastructure ควรผ่านขั้นตอนต่อไปนี้:

```text
Change
  ↓
Git
  ↓
Terraform init for the selected backend
  ↓
Terraform fmt
  ↓
Terraform validate
  ↓
Static / security checks
  ↓
Terraform plan saved to a protected file
  ↓
Review the exact plan, target account, zone and workspace
  ↓
Authorized operator approval bound to the plan SHA-256
  ↓
Apply the same saved plan after digest verification
  ↓
Cloudflare
  ↓
Post-deployment validation
```

กำหนด variables อย่างชัดเจน ตรวจสอบค่าด้วย validation ใช้ least privilege แยก environments ปกป้อง Terraform state ทำ CI validation ตรวจ drift และแยก secrets ออกจาก source code ห้าม commit production credentials ลง Git การเรียก `terraform validate` ต้องเกิดหลัง initialize backend และ providers; ใช้ `scripts/cloudflare-apply.sh` เพื่อให้ลำดับนี้ถูกต้องและเก็บ plan ไว้เป็นไฟล์ mode 0600

ตรวจ plan ทั้งหมด พร้อม target account, zone, workspace, backend และ feature flags ก่อนอนุมัติ helper จะสร้าง manifest mode 0600 ที่ผูก plan SHA-256 กับ account, zone, workspace, backend,
ไฟล์ `.env.cloudflare`, Terraform source, tfvars, lockfile และ feature flags พร้อมพิมพ์ Approval SHA-256 สำหรับ `--approved-plan-sha256` การ apply ตรวจ digest และ target ปัจจุบันก่อนเริ่ม backend แล้ว apply สำเนาส่วนตัวของ plan เดิมเท่านั้น โดยไม่ import DNS หรือสร้าง plan ใหม่ หาก plan, manifest, target, backend, environment หรือ Terraform configuration เปลี่ยน ให้สร้าง plan ใหม่และขอการอนุมัติใหม่ หลัง apply helper ตรวจ `https://zwf.zeaz.dev/health` และ Z.A.R.V.I.S. public routes แบบ fail-closed จากนั้นตรวจ ZEAZ One endpoints ตาม feature flags ที่ผูกไว้ใน manifest workflow `HA Infrastructure` ทำได้เฉพาะ plan และไม่มี production apply path การเข้าถึง repository หรือคำสั่งจาก agent ไม่ถือเป็น authorization สำหรับ apply

## การเชื่อมโยง hostname กับบริการ

สำหรับ production hostname แต่ละรายการ ควรตรวจสอบข้อมูลต่อไปนี้:

- วัตถุประสงค์ของ hostname
- บริการและ repository ที่เป็นเจ้าของ
- environment ที่ใช้งาน
- ตำแหน่งของ origin
- สถานะ Cloudflare proxy
- การใช้ Cloudflare Tunnel
- Terraform resource ที่จัดการ
- security และ access controls ที่บังคับใช้
- health/readiness checks ที่ใช้ตรวจสอบ
- วิธี deploy, rollback และ recovery

ความสัมพันธ์ที่ต้องการ:

```text
Hostname
   ↓
Terraform resource
   ↓
Cloudflare zone / edge configuration
   ↓
DNS / Tunnel / Access / security policy
   ↓
Origin service
   ↓
Health validation
```

production DNS records ที่ไม่ทราบที่มา ซ้ำซ้อน หรือสร้างด้วยมือเป็น infrastructure debt ต้องสืบหาที่มาและผลกระทบก่อน ห้ามลบโดยคาดเดา

เมื่อสร้าง plan บน GitHub Actions runner ไฟล์ saved plan อยู่บน runner ชั่วคราวและไม่ได้ถูกเผยแพร่เป็น artifact สำหรับ apply; การ apply จริงต้องสร้างและ review plan บนเครื่อง operator ที่ได้รับอนุญาต แล้วใช้ไฟล์เดิมกับ digest ที่ตรงกัน

## ความรับผิดชอบของ zWorkforce

zWorkforce เป็น control layer สำหรับ AI workforce และ automation ในระบบนิเวศ ZeaZDev บทบาทที่เกี่ยวข้องประกอบด้วย:

- Architect
- Developer
- Code Reviewer
- Security
- QA/Test
- DevOps
- Terraform
- Cloudflare
- Documentation
- Repository Auditor
- CI/CD
- Production Readiness

ก่อนแก้ไข agents ต้องตรวจสอบสถานะปัจจุบันและรักษาสถาปัตยกรรมกับ public interfaces เดิม เว้นแต่คำขอจะระบุให้เปลี่ยนโดยชัดเจน

## ขั้นตอนควบคุมความปลอดภัยของการเปลี่ยนแปลง

การเปลี่ยน Cloudflare, Terraform, DNS, Tunnel, authentication, networking หรือ production ต้องมีการวิเคราะห์ผลกระทบและความปลอดภัยอย่างชัดเจน

ก่อนทำการเปลี่ยนแปลง ให้ระบุ:

1. resource ที่ได้รับผลกระทบ
2. hostname ที่เกี่ยวข้อง
3. environment ที่ได้รับผลกระทบ
4. origin ที่เกี่ยวข้อง
5. พฤติกรรม DNS
6. ผลต่อ traffic routing
7. ผลต่อ Tunnel ingress
8. ผลต่อ security policy
9. ระยะเวลาหรือโอกาสที่บริการหยุดชะงัก
10. วิธี rollback หรือ recovery

ขั้นตอนที่แนะนำ:

```text
Inspect → Understand → Validate → Plan → Review impact → Apply → Verify
```

ห้ามทำ destructive infrastructure changes เพียงเพราะ configuration ดูไม่สอดคล้องกัน

## หลักการด้าน Security

ZeaZDev และ zWorkforce ยึดหลักต่อไปนี้:

- Least privilege
- Zero-trust principles เมื่อเหมาะสม
- แยก secrets ออกจากข้อมูลทั่วไป
- จัดการ credentials อย่างปลอดภัย
- ห้ามเก็บ production secrets แบบ plaintext ใน Git
- ใช้ authentication ที่เข้มแข็งและ authorization ที่ชัดเจน
- รักษาความปลอดภัยของ API boundaries
- ตรวจสอบ dependencies และ containers
- ตรวจสอบ infrastructure ก่อนใช้งาน
- เก็บ audit trail
- ทำ automation อย่างปลอดภัย

การเข้าถึง repository ไม่ได้ให้อำนาจทำ destructive infrastructure operations โดยอัตโนมัติ

## Local-first และการควบคุมต้นทุน

ลำดับทางเลือกด้าน infrastructure ที่ต้องการ:

```text
Existing hardware
    >
Self-hosted infrastructure
    >
Open-source software
    >
Free tiers
    >
Paid services only when justified
```

การตัดสินใจด้าน architecture ควรคำนึงถึงค่า compute, storage, network, API/model, Cloudflare, managed services และ operational costs หลีกเลี่ยง vendor lock-in และ managed services ที่ไม่จำเป็น เมื่อมีทางเลือก self-hosted ที่เชื่อถือได้

## เกณฑ์ Production readiness

Production readiness ครอบคลุมมากกว่าการ build ผ่าน ควรตรวจสอบหัวข้อที่เกี่ยวข้องดังนี้:

### Application

- Functional correctness
- API contracts
- Authentication และ authorization
- Error handling
- Data integrity

### Infrastructure

- Reproducible deployment
- Terraform validation
- Cloudflare configuration
- DNS correctness
- Tunnel routing
- Origin health

### Security

- Secrets
- Dependencies
- Access control
- Network exposure
- Container configuration
- Security policies

### Operations

- Logging
- Metrics และ tracing เมื่อเกี่ยวข้อง
- Health/readiness checks
- Backup และ recovery
- Rollback
- Operational documentation

### Engineering

- Automated tests
- CI/CD
- Code quality
- Documentation
- Dependency management
- Version control และ traceability

## แหล่งอ้างอิงสถานะระบบ

```text
Git Repository
      │
      ├── Terraform
      ├── Application Code
      ├── CI/CD
      ├── Configuration
      ├── Contracts
      └── Documentation
             │
             ▼
         Deployment
             │
             ▼
        Cloudflare
             │
             ▼
      Runtime Environment
```

runtime state ใช้ยืนยันสิ่งที่สังเกตพบ ณ เวลานั้น ส่วน Git/Terraform แสดง desired state; ให้ตรวจพบ ทำความเข้าใจ และแก้ drift อย่างตั้งใจ runtime probes หรือผลจาก terminal ที่ไม่ได้เก็บเป็นหลักฐานถาวรเป็น operational observation เท่านั้น และห้ามใช้ปิด release gate สำหรับ gate ที่กำหนด external evidence ให้บันทึก environment, timestamp, command/run reference, result และ durable artifact/reference โดยผูกกับ exact candidate SHA ใน docs/PRODUCTION-EVIDENCE.md จนกว่าจะบันทึกครบ ให้คงสถานะ PENDING EXTERNAL EVIDENCE; CI output, source code และ transient observations ใช้แทนหลักฐานดังกล่าวไม่ได้

## แนวทางปฏิบัติสำหรับ agents

agents ที่ทำงานกับระบบนิเวศ ZeaZDev ควรปฏิบัติงานตามลำดับ:

```text
Discover
→ Analyze
→ Plan
→ Implement
→ Test
→ Review
→ Secure
→ Document
→ Validate
```

เลือกการเปลี่ยนแปลงที่ปลอดภัยและเล็กที่สุดซึ่งแก้ปัญหาได้ครบ หลีกเลี่ยง implementation ซ้ำซ้อน abstractions หรือ dependencies ที่ไม่จำเป็น placeholders, tests ปลอมหรือถูกปิดใช้งาน, hardcoded secrets, configuration ที่ต้องทำด้วยมือเท่านั้น, Terraform ที่ไม่ผ่าน validation และการทำให้ระบบอื่นเสียหายโดยไม่เกี่ยวข้อง

## เป้าหมายหลัก

ทำให้ zWorkforce เป็นชั้น engineering และ automation ที่เชื่อมโยง agent actions กับ repository, Terraform configuration, Cloudflare resources, hostname ภายใต้ zeaz.dev, origin services และ production validation ได้อย่างปลอดภัย

```text
                    ZEA ZDEV ECOSYSTEM
                           │
                           ▼
                      ZWorkforce
                           │
          ┌────────────────┼────────────────┐
          │                │                │
       Software        Infrastructure      AI
       Engineering      Automation       Workforce
          │                │                │
          ▼                ▼                ▼
       GitHub          Terraform       Agents / Skills
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                       Cloudflare
                           │
                           ▼
                     *.zeaz.dev
                           │
                           ▼
                  Production Services
```

เอกสารนี้ให้บริบทของระบบนิเวศเท่านั้น ไม่ใช้แทน repository security policy, Terraform-specific rules, Cloudflare provider documentation, deployment runbooks หรือ operational documentation ของแต่ละ application
