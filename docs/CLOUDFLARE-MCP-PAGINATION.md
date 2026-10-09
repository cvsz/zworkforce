# Cloudflare MCP — Pagination

ฟังก์ชัน `cloudflare.live_inventory` รับค่า `page` เป็นจำนวนเต็มตั้งแต่ 1 ถึง 10 โดยค่าเริ่มต้นคือ 1 ใช้ HTTP GET ไปยัง Cloudflare API เท่านั้น และส่งข้อมูลไม่เกิน 50 รายการต่อหน้า

ระบบส่ง `has_more` เมื่อ Cloudflare มีจำนวนหน้าหรือ `total_count` ที่ตรวจสอบได้ สำหรับ `zones` ระบบเรียก `GET /zones/{zone_id}` เฉพาะ Zone ID ที่อยู่ใน Tenant Allowlist โดยใช้หนึ่ง Zone ต่อหน้าและคำนวณ `has_more` จาก Allowlist เท่านั้น ไม่เรียก Pagination ของ Provider ทั้งหมด

ทุก Response มี `partial: true` และ **ไม่รับประกันว่าเป็น Inventory ทั้งหมด** โดยไม่มีการทำ Retry อัตโนมัติหรือบันทึก Durable Audit ใน Phase นี้

ดูรายละเอียดการตั้งค่าและข้อจำกัดที่ [Cloudflare Live Read-only MCP](CLOUDFLARE-LIVE-READONLY-MCP.md)
