# Cloudflare Terraform Stack

This stack ports the active Cloudflare DNS-to-Tunnel ownership model from `cvsz/zeaz-platform` into `z-platform`.

## Scope

- Cloudflare provider v5.
- Proxied CNAME records targeting an existing Cloudflare Tunnel.
- A validated application-route contract.
- Generated cloudflared ingress and Phase 6 readiness URLs.
- Optional remote tunnel ingress ownership behind an explicit `manage_tunnel_config` safety switch.
- No credentials, Terraform state, legacy backups, stale resources, or account tokens are copied.

The tunnel itself remains an existing account resource. The remote ingress configuration can be managed only after the current configuration is imported and reviewed; this avoids replacing a live connector accidentally.

## Authentication

Use a scoped token through the environment. Never place it in a committed tfvars file.

```bash
export TF_VAR_cloudflare_api_token="$CLOUDFLARE_API_TOKEN"
```

Required permissions should be limited to the managed account/zone and the resources used by the plan.

## Configure

```bash
cd infrastructure/terraform/cloudflare
cp terraform.tfvars.example terraform.tfvars
chmod 600 terraform.tfvars
$EDITOR terraform.tfvars
```

Replace every zero/sample value with the real Cloudflare account ID, zone ID, tunnel UUID, hostnames, origins, and Access allow-list metadata.

## Validate and plan

```bash
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -out=tfplan
terraform show -no-color tfplan
```

To adopt the existing remote-managed ingress safely, first set `manage_tunnel_config = true` only in an uncommitted operator tfvars file, import the existing configuration, and review the plan:

```bash
terraform import cloudflare_zero_trust_tunnel_cloudflared_config.platform[0] "<account-id>/<tunnel-id>"
terraform plan -out=tfplan
terraform show -no-color tfplan
```

Review DNS ownership before applying. Existing records must be imported rather than duplicated:

```bash
terraform import 'cloudflare_dns_record.app_routes["phase6"]' '<zone-id>/<record-id>'
```

## Apply

```bash
terraform apply tfplan
terraform output -json cloudflared_ingress
terraform output -json phase6_urls
```

When `manage_tunnel_config` is false, merge the `cloudflared_ingress` output into the remotely managed tunnel configuration owned by operations. When it is true, Terraform applies the ingress directly. The terminal `http_status:404` rule must remain last.

## Free-mode Access

This stack intentionally does not create WAF, API Shield, Workers, R2, or D1 resources. Those products are not part of the account's approved Free-mode baseline. Set `manage_free_access = true` only after reviewing the Access application plan and confirming the route email allow-lists. Protected routes use the configured email allow-list and can require MFA. Supply an existing `free_access_allowed_idps` list when the account requires a specific identity provider.

Access applications are managed as nested policies in `free-access.tf`; import existing Access applications before enabling management to avoid duplicate applications.

### Locally managed cloudflared connectors

If the connector runs from a local `cloudflared` service with a checked-in or operator-owned ingress file, merge [`cloudflared-observability-ingress.yml.example`](./cloudflared-observability-ingress.yml.example) into that file before the wildcard route. Terraform's remote tunnel configuration does not rewrite a connector that is explicitly running with local ingress configuration. The connector must use `127.0.0.1:80` when it runs on the same host as Caddy.

## Cloudflare-proxied Phase 6

With the tunnel route in place, Caddy/ACME is not required for `phase6.zeaz.dev`. Cloudflare terminates public TLS and sends traffic through the tunnel to `http://phase6-api:8080`. This avoids exposing ports 80/443 on the private host.

The GitHub webhook receiver lives on the same host at `https://${var.app_routes.phase6.hostname}/webhooks/github`. Configure GitHub with a repository webhook secret and point the delivery URL at that exact path.

Access policy resources are intentionally not created in this first port because the legacy repository contains competing provider-generation ownership models. `access_enabled` and allow-list metadata are validated now and are the contract for a follow-up Access module after the current account resources are imported and reconciled.
