# CMe Production Operator Contract / สัญญาผู้ดูแลการผลิต CMe

zWorkforce manages only the CMe-specific edge resources explicitly declared in this repository's Terraform and ingress contracts. Ownership of other `zeaz.dev` resources is not implied. The CMe repository owns its application, database behavior, and application verification commands.

## Edge contract / ขอบเขต edge

- Public host: `cme.zeaz.dev`
- Managed DNS: ใช้ `cloudflare_dns_record.cmeerp` ที่มีอยู่แล้วใน `infrastructure/terraform/cloudflare/main.tf`; ห้ามสร้าง state address ของ Terraform ซ้ำ
- Cloudflare Access protection: `infrastructure/terraform/cloudflare/cme.tf`
- Tunnel ingress: `deploy/cloudflare/tunnel-ingress.yml`
- Reviewed loopback origin: `http://127.0.0.1:8001`

ห้ามใส่ database credentials, session secrets หรือ Cloudflare credentials ของ CMe ไว้ในไฟล์ของ repository

Do not place CMe database credentials, session secrets or Cloudflare credentials in repository files.

## Change procedure / ขั้นตอนการเปลี่ยนแปลง

1. Freeze commit/image digest ของ CMe ที่จะ deploy ให้ชัดเจน
2. รัน Terraform plan จาก Cloudflare stack ด้วย credentials ของ operator แล้วเก็บ plan artifact ไว้
3. ขอ production-change approval อย่างชัดแจ้งสำหรับ Terraform plan/digest ที่บันทึกไว้ ก่อน apply Cloudflare mutations ใด ๆ
4. Preserve a protected pre-change Terraform state snapshot, current Access policies, and a reviewed rollback design. Apply only the approved immutable forward plan. After apply, generate a new rollback plan against the actual post-apply state, review its complete resource delta, obtain separate rollback authorization, and retain its digest. Never execute a stale plan built against pre-apply state.
5. Deploy CMe artifact ที่ระบุชัดเจนไปยัง loopback origin ที่ผ่านการทบทวนแล้ว
6. เปิดเผย identity ของ commit/image ที่ deploy แล้วแบบ immutable จาก runtime/deployment metadata endpoint ที่คืน JSON `{"release": "<digest-or-sha>"}` และผูกกับ deployment ที่ให้บริการอยู่จริง ไม่ใช่ไฟล์ที่ operator เขียนเอง
7. Export machine-verification Access credentials จาก operator secret store ที่ได้รับการป้องกันเป็น `ZWORKFORCE_ACCESS_ID` และ `ZWORKFORCE_ACCESS_TOKEN`; ห้ามเขียนลงไฟล์ repository หรือ evidence
8. รันทุกครั้งด้วย output path ใหม่เสมอ:
   `python3 scripts/verify-cme-production.py --expected-release <digest-or-sha> --runtime-release-url <https-runtime-metadata-url> --operator <operator-id> --approval-reference <approval-id> --terraform-plan-reference <plan-sha-or-uri> --terraform-apply-reference <apply-run-id> --deployment-reference <deployment-run-id> --alert-receipt <alert-delivery-id> --output <immutable-evidence.json>`
9. เก็บ JSON evidence พร้อม operator identity, Terraform plan/apply reference, deployment reference และ alert receipt
10. Drill the separately approved post-apply Cloudflare rollback plan when edge changes cause an incident. Verify restored Access/DNS and operator connectivity. Separately roll back the previous CMe artifact when application changes cause the incident; verify runtime health and measure recovery time. Recreate plans when Terraform state changes. Never apply a stale reverse plan or alter state ad hoc.

## Required operator inputs

The operator must obtain `CME_ACCESS_ALLOWED_EMAILS` and `CME_ACCESS_SERVICE_TOKEN_ID` from the approved CMe Access configuration before running the Terraform wrapper. These are protected operational inputs, not sample credentials; do not print secret material in logs. Preserve the corresponding Access application and policy evidence.

## Non-goals

- CMe machine-verification secrets จะไม่ถูกผูกเข้า automated workflow ใด ๆ (รวมถึง `ha-infrastructure.yml`) การ apply  production ทำโดย operator ด้วยมือเท่านั้น ตามขั้นตอนด้านบน

## Required PASS evidence / หลักฐาน PASS ที่ต้องมี

การ GO การผลิตของ CMe ต้องมี evidence ที่เป็นปัจจุบันสำหรับ exact artifact identity, DNS resolution, trusted TLS, health, readiness, PostgreSQL restore/rollback พร้อม RPO/RTO ที่วัดได้, load threshold จาก workload, production monitoring/alert delivery และการหมุนเวียน runtime credential/secret

A CMe production GO requires current evidence for exact artifact identity, DNS resolution, trusted TLS, health, readiness, PostgreSQL restore/rollback with measured RPO/RTO, workload-derived load thresholds, production monitoring/alert delivery, and runtime credential/secret rotation.

การตั้งค่าใน repository ไม่ใช่หลักฐานว่า Cloudflare หรือ production infrastructure ถูก apply แล้ว จนกว่าจะมี approved operator apply และ post-action verification ที่เก็บไว้ gate เหล่านั้นถือว่ายังรอ external evidence อยู่

Repository configuration is not proof that Cloudflare or production infrastructure has been applied. Until an approved operator apply and post-action verification are retained, those gates remain pending external evidence.
