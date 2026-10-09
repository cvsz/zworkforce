# Cloudflare Live Read-only MCP

Adapter นี้เป็นการอ่าน Cloudflare API แบบ Opt-in ผ่าน Server เท่านั้น รองรับ `zones`, `dns_records` และ `tunnels` ไม่มีความสามารถในการแก้ไขทรัพยากร

## Configuration

กำหนดค่าผ่าน Server-side Environment หรือ Secret Manager เท่านั้น ห้ามใส่ Token ใน Git, Browser หรือ Prompt

```bash
export ZWORKFORCE_CLOUDFLARE_READ_TENANTS='{
  "tenant-a": {
    "zone_ids": ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
    "account_ids": ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
    "token_env": "ZWORKFORCE_CF_TOKEN_PRODUCTION"
  }
}'
```

ตัวอย่าง ID เป็น Placeholder ไม่ใช่หลักฐาน Ownership ต้องตรวจ Owner จาก `docs/CENTER-CONTROL-PLANE.md` ก่อนใช้งานจริง

## MCP Tool

`cloudflare.live_inventory` ใช้ `resource` เป็น `zones`, `dns_records` หรือ `tunnels`; สำหรับสองประเภทหลังต้องระบุ `resource_id` แบบ Hex 32 ตัวอักษรที่อยู่ใน Tenant Allowlist

ค่า `page` เป็น Integer ตั้งแต่ 1–10 (Default 1) ดู [Pagination Contract](CLOUDFLARE-MCP-PAGINATION.md)

ต้องมี Role `viewer` และ Scope `workforce:read` ตัว Adapter ใช้ HTTPS Endpoint ที่กำหนดตายตัว, GET-only, 8-second Timeout, 1 MiB Response Limit และไม่ตาม Redirects

ทุก Response มี `partial: true` ค่า `has_more` อาจเป็น `null` โดยเฉพาะ `zones` เพื่อป้องกันการเปิดเผยจำนวน Zone ข้าม Tenant ห้ามตีความผลเป็น Complete Inventory

## Operational Gates

ใช้ API Token แบบ Least Privilege: `Zone Read`, `DNS Read` และ/หรือ `Cloudflare Tunnel Read` โดยจำกัด Resource จริง ต้องตรวจ Ownership และทดสอบ Live Staging ก่อนเปิด Production ระบบนี้ไม่รองรับ Mutation และยังไม่มี Durable Audit หรือ Automatic Retry

## Tests

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_live_mcp.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_pagination_mcp.py' -v
python3 -m compileall -q zworkforce tests
```
