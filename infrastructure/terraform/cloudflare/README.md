# Moopiew Cloudflare Terraform

This stack follows the Cloudflare Tunnel DNS ownership model used by
`z-platform`: proxied CNAMEs send `moopiew.zeaz.dev`, `arin.zeaz.dev`, `zttshop.zeaz.dev`,
`piewdash.zeaz.dev`, `qwen.zeaz.dev`, `chat.zeaz.dev`, `zerp.zeaz.dev`, and
`cme.zeaz.dev` to
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

## Safe setup

```bash
cp .env.cloudflare.example .env.cloudflare
chmod 600 .env.cloudflare
$EDITOR .env.cloudflare
./scripts/cloudflare-plan.sh
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
./scripts/cloudflare-plan.sh
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

The plan script never applies. If any hostname already exists, import it
before planning to prevent Terraform from attempting to create a duplicate:

The canonical public zWorkforce hostname managed by this stack is
`zwf.zeaz.dev`, represented by the single `cloudflare_dns_record.zwf` resource.
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
./scripts/cloudflare-plan.sh
```

Only after review, an operator may apply `tfplan` manually. Keep
`manage_tunnel_config = false` unless all existing ingress rules have first
been imported and reviewed. For a local cloudflared configuration, merge the
rendered `cloudflared_ingress` output before its final fallback rule. The
reviewed origins are deliberately restricted to `127.0.0.1`: application
traffic uses Caddy port 8080 and dashboard and ERP traffic uses authenticated
Caddy port 80; zERP traffic uses Caddy port 80 and is forwarded to port 3001.
