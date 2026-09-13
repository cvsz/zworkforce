# zNeonDrive — `zneon.zeaz.dev`

This stack manages the Cloudflare DNS and optional Cloudflare Tunnel ingress for the public zNeonDrive website.

## Managed resources

- DNS: `zneon.zeaz.dev` → existing Cloudflare Tunnel CNAME (`*.cfargotunnel.com`), proxied through Cloudflare.
- Tunnel ingress: `zneon.zeaz.dev` → `http://127.0.0.1:18081`.
- Public URL output: `zneon_url`.

The origin is intentionally restricted to host loopback. The zNeonDrive Compose stack publishes the hardened nginx web frontend on `127.0.0.1:18081`; Cloudflare Tunnel is the intended public entry point.

## Safe rollout

`manage_tunnel_config` remains `false` by default. DNS can be managed independently, but do **not** enable Terraform management of the full remote tunnel configuration until the existing Cloudflare tunnel ingress has been imported/reconciled and reviewed. Enabling it blindly can replace unrelated ingress entries.

From `/home/cvsz/platforms/zworkforce/infrastructure/terraform/cloudflare`:

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan
```

Supply Cloudflare credentials through environment variables/secrets according to the parent README; do not commit API tokens or populated `terraform.tfvars` files.

When the existing remote ingress is known to match this Terraform stack, plan with tunnel management enabled and inspect the complete ingress diff before apply:

```bash
terraform plan -var='manage_tunnel_config=true'
terraform apply -var='manage_tunnel_config=true'
```

After apply, verify:

```bash
curl -fsSI https://zneon.zeaz.dev/
curl -fsS https://zneon.zeaz.dev/healthz
curl -fsS https://zneon.zeaz.dev/api/healthz
```

Expected origin health is served by the zNeonDrive web stack at `127.0.0.1:18081`. This domain configuration does not make the game runtime production-ready; it only publishes the website through the existing Cloudflare Tunnel boundary.
