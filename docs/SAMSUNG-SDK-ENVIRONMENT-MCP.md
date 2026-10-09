# Samsung SDK Environment MCP

เพิ่ม Tool `samsung.sdk_environment` สำหรับตรวจการตั้งค่า Environment ของ Samsung SDK ฝั่ง Server แบบ Read-only โดยไม่รันคำสั่งใด ๆ และไม่เชื่อมต่อกับ TV

สำหรับ `samsung-legacy` ตรวจ `SAMSUNG_LEGACY_SDK_HOME` และสำหรับ `tizen` ตรวจ `TIZEN_STUDIO_HOME` หรือ `TIZEN_SDK_HOME` เท่านั้น

ผลลัพธ์ระบุว่าตั้งค่า Path หรือมี Directory หรือไม่ แต่ **ไม่ยืนยัน** SDK Version, Signing, Package Compatibility หรือ Device Installation ข้อมูล Path ไม่ถูกแสดงออกไปผ่าน MCP

Tool ใช้สิทธิ์ `viewer` และ `workforce:read` เท่านั้น ขั้นตอนต่อไปคือการตรวจ SDK Version และ Signed Package แบบแยก Process ที่ได้รับอนุมัติ

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_samsung_sdk_probe_mcp.py' -v
```
