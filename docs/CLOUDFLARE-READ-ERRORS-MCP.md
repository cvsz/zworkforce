# Cloudflare API Error Handling

เพิ่มการจัดการ Cloudflare API HTTP `429`, `401`, `403` และข้อผิดพลาด HTTP อื่นอย่างชัดเจน โดยไม่มีการส่ง Token, URL หรือ Response Body ของ Provider ไปยัง MCP Client

`429` แสดงข้อผิดพลาด Rate Limit และให้ Operator Retry ภายหลัง โดย **ไม่ทำ Automatic Retry** ซึ่งอาจทำให้เกิด API Flooding

`401` และ `403` แสดง Permission Error แบบไม่เปิดเผยรายละเอียด Token

ไม่มีการเพิ่ม Mutation, Production Token หรือ Live Verification ใน PR นี้

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_read_errors_mcp.py' -v
```
