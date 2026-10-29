# Runbook: Z.A.R.V.I.S. Voice Service-Token Rotation

## สถานะและขอบเขต

ใช้เอกสารนี้เมื่อพบว่า voice service token เคยถูก commit เป็น literal fallback หรือไม่สามารถยืนยันได้ว่าไม่เคยถูกใช้งาน ให้ถือว่า token เดิมถูกเปิดเผยแล้ว แม้จะลบออกจาก working tree หรือเพิ่ม fix ใน branch แล้วก็ตาม เพราะ Git history ยังเก็บค่าประวัติไว้ได้

เอกสารนี้เป็น operator runbook เท่านั้น การแก้ไข source code หรือ CI ไม่ได้หมุน secret ใน environment จริง และไม่ใช่การอนุมัติให้เปลี่ยน production secret

## Preconditions

- มี change ticket/approval และระบุเจ้าของ voice gateway กับ zWorkforce runtime
- ระบุ secret-manager entries และ deployment bindings ที่ใช้งานจริงโดยไม่คัดลอกค่า secret ลง ticket, chat, terminal transcript หรือ GitHub comment
- มี canary/smoke test ที่ได้รับอนุมัติสำหรับ voice gateway และมี rollback window
- บันทึก candidate SHA, deployment target, approver และ UTC timestamp

## Procedure

1. ตรวจสอบจาก secret manager และ deployment configuration ว่า token เดิมเคยถูก provision หรือไม่ ห้ามแสดงค่าจริงใน terminal output หรือ log
2. หากเคยใช้หรือพิสูจน์ไม่ได้ว่าไม่เคยใช้ ให้สร้าง token ใหม่ด้วย secret manager/approved generator และตรวจว่ามี non-whitespace อย่างน้อย 32 characters โดยไม่พิมพ์ token ออกมา
3. อัปเดต verifier/consumer ของ voice gateway และ zWorkforce ผ่าน secret-manager binding ที่มีอยู่ตามลำดับ rollout ที่อนุมัติไว้ ห้าม commit ค่า secret หรือส่งผ่าน command-line argument ที่บันทึกใน process list/history
4. Restart/rollout เฉพาะ service ที่อยู่ใน change scope และตรวจ readiness/health โดยไม่แสดง environment variables
5. รัน canary ด้วย credential ใหม่: ต้องผ่านตาม contract ที่อนุมัติ
6. รัน negative test ด้วย credential เดิมผ่านวิธีที่ปลอดภัยและไม่บันทึกค่า: ต้องถูกปฏิเสธ ห้ามบันทึก request header หรือ secret ใน output
7. ทดสอบ missing/short token: เมื่อ voice ถูกเปิดใช้งานโดยไม่มี token ที่ถูกต้อง startup ต้อง fail closed; หากไม่มี secret ใหม่ ให้ปิด voice อย่างชัดเจนแทนการใช้ fallback
8. ตรวจ logs/audit events เพื่อยืนยันว่าไม่มี token material, Authorization header หรือ .env.ai content ถูกบันทึก

## Evidence to retain

บันทึกเฉพาะข้อมูลที่ไม่เป็นความลับ:

- UTC start/end timestamp และผู้อนุมัติ
- Repository commit SHA และ deployment/artifact digest ที่ตรวจสอบแล้ว
- Secret-manager version/reference identifier (ห้ามบันทึก secret value)
- ผล canary ด้วย token ใหม่ และผล negative test ที่ยืนยันว่า token เก่าถูกปฏิเสธ
- ผล missing/short-token fail-closed test
- Redacted log/audit reference และ rollback outcome

หากไม่สามารถพิสูจน์การปฏิเสธ token เก่าได้ ให้คง incident/rotation gate เป็น OPEN และห้ามเปิด voice ใน production

## Rollback

- หาก rollout ใหม่ล้มเหลว ให้ปิด voice ด้วย ZWORKFORCE_ZARVIS_VOICE_ENABLED=false และคง core service ไว้เฉพาะเมื่อ health/authorization checks ผ่าน
- ห้าม rollback ด้วยการคืน literal token ที่เคย commit
- หากต้อง rollback credential ให้สร้าง/เลือก secret version ใหม่ที่ผ่านการอนุมัติ แล้วทดสอบ canary และ old-token rejection ซ้ำ
- หากพบ token ใน log ให้เก็บหลักฐานแบบ redacted, จำกัดสิทธิ์เข้าถึง log และดำเนิน incident-response process ขององค์กร

## Automation boundary

Automated code changes may remove fallbacks and add tests. Production secret rotation, credential revocation, service restart and externally visible traffic changes require an authorized operator and recorded change approval.
