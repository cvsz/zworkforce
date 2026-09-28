# Deploy Moopiew through Cloudflare Tunnel

The project uses the same split of responsibilities as z-platform:

1. Terraform owns the proxied DNS CNAMEs for the public application hosts,
   including `chat.zeaz.dev` for OpenWebUI.
2. An existing Cloudflare Tunnel owns the public-to-private connection.
3. `cloudflared` forwards the application to Caddy on `127.0.0.1:8080`.
4. `cloudflared` forwards the dashboard hostname to Caddy on
   `127.0.0.1:80`; Caddy applies Basic Auth and proxies to
   `127.0.0.1:8082`.
5. Cloudflare Access and Caddy Basic Auth protect `piewdash.zeaz.dev`.

The Arin frontend is built from `sites/arin`, published to `deploy/arin`, and
served by the host-specific Caddy route for `arin.zeaz.dev` on the same
reviewed loopback origin. Caddy proxies Arin's `/api/*`, `/preview/*`, and
`/app/*` paths to the separate loopback backend on `127.0.0.1:8787`; Arin data
is kept in the ignored `data/arin/` directory and never shares MooPiew's
database.

OpenWebUI is published through the same tunnel at `chat.zeaz.dev` and reaches
the host-published container port `127.0.0.1:3000`. Keep the tunnel origin on
the host port; the container's internal port `8080` is not the tunnel target.

## Required operator values

Populate `.env.cloudflare` locally from the Cloudflare account that owns
`zeaz.dev`:

- `CLOUDFLARE_API_TOKEN`: scoped to the account/zone, with Zone DNS Edit,
  read/edit permission for the selected existing tunnel, and Account Access:
  Apps and Policies Edit.
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_ZONE_ID`, and `CLOUDFLARE_TUNNEL_ID`.
- `CLOUDFLARE_TUNNEL_TOKEN`: only on the origin host that runs cloudflared.
- `PIEWDASH_ACCESS_ALLOWED_EMAILS`: a JSON array containing exact operator
  emails. Never use an `everyone` or domain-wide Access rule.
- `MOOPIEW_ORIGIN=http://127.0.0.1:8080` and
  `PIEWDASH_ORIGIN=http://127.0.0.1:80`. The latter must never point directly
  to port 8082 because that bypasses Caddy Basic Auth.

The API token and tunnel token are distinct secrets. Never commit either one.

## Provision safely

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./scripts/start.sh
./scripts/cloudflare-apply.sh --skip-import
```

หาก Cloudflare มี record ของ hostname อยู่แล้ว ให้ import record นั้นก่อน
สร้าง plan เพื่อ review ตรวจว่า CNAME ยังคง proxied และชี้ไปยัง tunnel
ที่เลือกไว้ คงค่า `manage_tunnel_config = false`; ให้นำ ingress fragment
ที่สร้างขึ้นไปรวมกับ tunnel config เดิม เว้นแต่จะ import และ review remote
configuration ทั้งหมดแล้ว

ตรวจ saved plan และ target ทั้งหมด helper จะสร้าง manifest แบบ protected ที่
ผูก plan digest กับ Cloudflare account, zone, workspace, backend,
`.env.cloudflare`, Terraform source, tfvars, lockfile และ ZEAZ One feature flags
JSON จาก `terraform show -json` ส่งเข้า helper โดยตรงและไม่บันทึกลง disk ให้ apply
ด้วยคำสั่งที่ `cloudflare-apply.sh` พิมพ์ออกมาเท่านั้น
helper จะตรวจ approval digest, target และ configuration ปัจจุบันก่อน apply
saved plan เดิม หากค่าเหล่านี้เปลี่ยนให้สร้าง plan ใหม่ ห้ามเรียก
`terraform apply` โดยตรง

Start the connector on the origin host with:

```bash
./scripts/cloudflare-tunnel.sh
```

For durable user services, copy `deploy/systemd/moopiew.service`,
`deploy/systemd/moopiew-dashboard.service`, and
`deploy/systemd/moopiew-cloudflared.service` to `~/.config/systemd/user/`.
Install `deploy/systemd/moopiew-proxy-system@.service` under
`/etc/systemd/system/`; this system template runs Caddy as the selected user
with only the low-port bind capability. Then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now moopiew.service moopiew-dashboard.service moopiew-cloudflared.service
sudo systemctl daemon-reload
sudo systemctl enable --now "moopiew-proxy-system@$USER.service"
```

Create `.env.production` from its example and set unique role keys first. Keep
payment and Cloudflare credentials in separate ignored files. Create
`.env.dashboard` from its example, generate a random password and its Caddy
bcrypt hash, and keep the file mode `0600`. Verify all paths with
`./scripts/production-check.sh`.

Then verify `https://moopiew.zeaz.dev/api/menu`,
authenticated `https://piewdash.zeaz.dev/api/health`, `/api/ready`, and the
`https://zerp.zeaz.dev/` application route, and the customer storefront. An anonymous dashboard request must receive a Caddy
`401` or a Cloudflare Access login redirect, never dashboard data. A 502
response indicates an unreachable origin; a 530 indicates that Cloudflare
cannot reach a healthy tunnel.

## Arin release and runtime

On the origin host, create the ignored runtime environment from
`sites/arin/.env.arin.example`, set a unique `ARIN_CONNECTOR_KEY`, and keep the
file mode `0600`. Install the user service and build the frontend:

```bash
install -m 600 sites/arin/.env.arin.example .env.arin
# Replace ARIN_CONNECTOR_KEY with a generated Fernet key before starting.
systemctl --user daemon-reload
systemctl --user enable --now arin.service
npm --prefix sites/arin test
install -d -m 700 deploy/arin
cp -a sites/arin/dist/. deploy/arin/
sudo systemctl reload "moopiew-proxy-system@$USER.service"
```

Verify the backend before opening the public hostname:

```bash
curl -fsS http://127.0.0.1:8787/api/health
curl -fsS https://arin.zeaz.dev/api/health
```

The complete backend flow is covered by
`PYTHONPATH=sites/arin python3 sites/arin/scripts/integration-smoke.py`.
