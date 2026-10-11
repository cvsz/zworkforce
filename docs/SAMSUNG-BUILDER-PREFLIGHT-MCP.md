# Samsung Builder Preflight MCP

เพิ่ม `samsung.builder_preflight` เพื่อประเมิน Prerequisites แบบ Read-only โดยใช้ Model และ Model Year ที่ระบุเอง ตรวจว่ามี SDK Directory หรือไม่ และบอก Checklist สำหรับการสร้าง Signed Package

เครื่องมือนี้ **ไม่เรียก SDK, ไม่ Sign, ไม่ Build, ไม่ส่ง Package ไป TV** และ `ready_to_build` จะเป็น `false` เสมอจนกว่าจะมี Verification/Approval Workflow แยกต่างหาก

สำหรับ UA40F5500AR จำเป็นต้องยืนยัน Firmware และ Samsung Legacy SDK จริงก่อน ไม่สามารถใช้ผล Preflight ยืนยันว่า USB Install ทำได้
