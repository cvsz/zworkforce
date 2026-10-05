# Moopiew Cloudflare Terraform

This stack follows the Cloudflare Tunnel DNS ownership model used by
`z-platform`: proxied CNAMEs send `moopiew.zeaz.dev`, `arin.zeaz.dev`, `zttshop.zeaz.dev`,
`piewdash.zeaz.dev`, `qwen.zeaz.dev`, `chat.zeaz.dev`, `zwsl.zeaz.dev`,
`zerp.zeaz.dev`, `cme.zeaz.dev`,
`dbc.zeaz.dev`, and
`zwf.zeaz.dev` to
an existing tunnel. Cloudflared forwards the public app hostnames to Caddy on
port 8080 and the dashboard and ERP hostnames to Caddy on port 80. The
OpenWebUI chat hostname is forwarded directly to its reviewed host-published
port 3000, matching the existing container mapping, rather than to the
container-only port 8080.
host-specific dashboard route applies Basic Auth before proxying to the
loopback dashboard process on port 8082. Never point the tunnel directly at
port 8082 because that bypasses the origin authentication layer. The zERP
hostname also terminates at Caddy port 80, which routes to the zERP web server
on port 3001.
Terraform also owns the dashboard's Cloudflare Access application. Its allow
policy accepts only the exact, nonempty email set supplied through
`PIEWDASH_ACCESS_ALLOWED_EMAILS`; domain-wide and `everyone` rules are
deliberately unsupported. Caddy Basic Auth protects the origin as a second
layer.

The stack accepts the tunnel ID as either its canonical UUID or the compact
32-character identifier used by the existing z-platform environment.
All DNS records are Cloudflare-proxied (`proxied = true`, automatic TTL), so
the origin is not published as a directly reachable DNS target.

สำหรับ `zwsl.zeaz.dev` Terraform ส่ง traffic ผ่าน Tunnel ไปยัง Caddy ที่
`127.0.0.1:80`; Caddy route `/api/v1/{models,chat/completions,messages,responses}`
ไป Provider ที่ `127.0.0.1:18086` และ route `/data/`, `/auth/` กับหน้า UI ไป
Open WebUI ที่ `127.0.0.1:18087` ให้ใช้ `make cloudflare-up` ใน zwslcore
เพื่อเตรียมพอร์ตเหล่านี้ ทั้งสอง service ต้อง bind เฉพาะ loopback
ห้ามชี้ Tunnel ตรงไปยัง Ollama หรือ LiteLLM

## Safe setup

```bash
cp .env.cloudflare.example .env.cloudflare
chmod 600 .env.cloudflare
$EDITOR .env.cloudflare
./scripts/cloudflare-apply.sh --skip-import
```

The API token needs Zone DNS Edit, Tunnel Read/Edit, and Account Access: Apps
and Policies Edit. `PIEWDASH_ACCESS_ALLOWED_EMAILS` must be a JSON array of
individual operator email addresses.

## Remote state

`backend.r2.tf.example` is the canonical encrypted S3-compatible R2 backend
with an S3 lockfile. The state script installs it as ignored `backend.tf` only
in R2 mode. A newly installed copy is removed only if initialization itself
fails; after initialization succeeds it remains in place even if subsequent
verification fails, because the remote backend may already be authoritative.
Bucket, endpoint and S3 credentials are partial configuration supplied only
from the mode-`0600` ignored `.env.cloudflare`; credentials are never written
to Terraform source or command-line backend arguments.

Keep `TERRAFORM_BACKEND_TYPE=local` and `ALLOW_R2_WRITE=false` until a private,
dedicated R2 bucket and a bucket-scoped Object Read & Write access pair exist.
Then take an independent copy of the current local state and migrate:

```bash
chmod 600 infrastructure/terraform/cloudflare/terraform.tfstate
TERRAFORM_BACKEND_TYPE=r2
ALLOW_R2_WRITE=true
TERRAFORM_STATE_BUCKET=replace-with-private-state-bucket
CLOUDFLARE_S3_API_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
CLOUDFLARE_ACCESS_KEY_ID=replace-with-bucket-scoped-access-key
CLOUDFLARE_ACCESS_SECRET_KEY=replace-with-bucket-scoped-secret
./scripts/cloudflare-state.sh migrate
./scripts/cloudflare-state.sh verify
./scripts/cloudflare-apply.sh --skip-import
```

Migration refuses a symlink, group/world-accessible state, an empty resource
set, or a state without a version-4 lineage. It stores a uniquely named
mode-`0600` backup and basename-only SHA-256 manifest in a mode-`0700` ignored
`output/backups/` directory. Verification requires the remote lineage and exact
managed resource-address set to match the local backup. Preserve the backup
and checksum together outside the origin host.

If migration initialization succeeds but verification fails, stop all
Terraform writers and leave `backend.tf` in place. Treat R2 as potentially
authoritative, run `./scripts/cloudflare-state.sh verify`, inspect the remote
lineage and resource addresses, and follow the recovery procedure in
[`RUNBOOK.md`](../../../RUNBOOK.md). Do not silently return to the local state.
Never disable `use_lockfile` to bypass a lock; investigate the current writer
first.

โหมด plan ของ `cloudflare-apply.sh` จะไม่ apply หาก hostname มีอยู่แล้ว ให้
import record ที่เกี่ยวข้องก่อนสร้าง plan เพื่อป้องกัน Terraform สร้างซ้ำ:

The canonical public zWorkforce hostname managed by this stack is
`zwf.zeaz.dev`, represented by the single `cloudflare_dns_record.zwf` resource.
`zslog.zeaz.dev` is a proxied route to the dedicated zslog fake-credit
realtime log service at `http://127.0.0.1:9581`. The service is demo-only and
does not connect to external games or handle real currency.
After a hostname migration, inspect the reviewed plan before applying it: the
canonical record must be retained, and only the explicitly retired legacy
record may be removed after the cutover has been validated. Do not edit
Terraform state JSON by hand.

```bash
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.moopiew "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.arin "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.zttshop "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.chat "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.piewdash "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.qwen "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.zerp "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.cmeerp "<zone-id>/<dns-record-id>"
terraform -chdir=infrastructure/terraform/cloudflare import \
  cloudflare_dns_record.dbc "<zone-id>/<dns-record-id>"
./scripts/cloudflare-apply.sh --skip-import
```

helper จะสร้าง saved plan และ manifest ที่อยู่ข้างกันโดยตั้ง permission เป็น
mode `0600` ตรวจ plan ทั้งหมด รวมถึง account, zone, workspace, backend,
`.env.cloudflare`, Terraform source, tfvars, lockfile และ feature flags ก่อนอนุมัติ
JSON จาก `terraform show -json` จะส่งเข้า helper โดยตรงและไม่บันทึกลง disk เพราะ
อาจมี sensitive values ค่า **Approval SHA-256** ที่พิมพ์ออกมาผูก bytes ของ saved
plan เข้ากับ manifest ให้ apply ด้วยคำสั่งที่ helper พิมพ์เท่านั้น
คำสั่งจะตรวจ digest และ target ปัจจุบันให้ตรงกับ manifest ก่อน apply สำเนา
ส่วนตัวของ saved plan เดิม หาก plan, manifest, target, backend, environment
หรือ Terraform configuration เปลี่ยน ให้สร้างและ review plan ใหม่ ห้ามเรียก `terraform apply` โดยตรงสำหรับ stack นี้
คงค่า `manage_tunnel_config = false` ไว้จนกว่าจะ import และ review ingress
rules เดิมทั้งหมด สำหรับ local cloudflared configuration ให้นำ output
`cloudflared_ingress` ที่ render แล้วไป merge ก่อน fallback rule ตัวสุดท้าย
origins ที่ review แล้วจำกัดไว้ที่ `127.0.0.1`: application traffic ใช้
Caddy port 8080 ส่วน dashboard และ ERP ใช้ authenticated Caddy port 80;
zERP traffic ใช้ Caddy port 80 และส่งต่อไป port 3001
