# HA Runtime VM x2 + Observability Topology

## Production topology

zWorkforce uses two independent runtime VMs behind a shared Supabase durable data plane, plus a dedicated observability runtime on VM-B.

- **VM-A (ha-a.zeaz.dev / 192.168.74.134):** primary zWorkforce runtime — API/control plane, scheduler, worker, outbox.
- **VM-B (ha-b.zeaz.dev / 192.168.74.135):** secondary zWorkforce runtime — API/control plane, scheduler, worker, outbox.
- **Observability (obs.zeaz.dev / 192.168.74.134):** OTel Collector, Prometheus, Alertmanager. Co-located on VM-B for this release.
- **Supabase (dryflnsxhjuaamnzfrtu):** shared durable PostgreSQL and Supabase Storage data plane. **Not an HTTP origin substitute.**
- **Vercel:** frontend / stateless web compute.

```text
Cloudflare
   |
   +-- zworkforce.zeaz.dev
   |       |
   |       +-- HA/load-balancing
   |             |
   |             +-- ha-a.zeaz.dev -> VM-A (192.168.74.134)
   |             +-- ha-b.zeaz.dev -> VM-B (192.168.74.135)
   |
   +-- obs.zeaz.dev -> VM-B observability (192.168.74.134)

VM-A                     VM-B
API (9456)               API (9456)
scheduler-A              scheduler-B
worker-A                 worker-B
outbox-A                 outbox-B
                         OTel agent
                         OTel Collector
                         Prometheus (19090)
                         Alertmanager (19093)
       \                  /
        +---- Supabase ---+
             PostgreSQL
             Auth
             Storage

Vercel
   -> frontend/stateless web
```

## Runtime identity and failover

Each VM must set a distinct `ZWORKFORCE_INSTANCE_ID`:

| VM | Hostname | INSTANCE_ID | Role |
| --- | --- | --- | --- |
| VM-A | ha-a.zeaz.dev | `vm-a` | primary runtime |
| VM-B | ha-b.zeaz.dev | `vm-b` | secondary runtime |

Scheduler leases and outbox ownership are held in the shared Supabase PostgreSQL database. Active/passive failover is implemented by the runtime lease mechanism, **not** by pointing traffic at Supabase.

Duplicate prevention is enforced by distinct `INSTANCE_ID` values. If both VMs claim the same identity, the release gate fails.

## Canonical routes

| Public host | Private origin | Role |
| --- | --- | --- |
| `zworkforce.zeaz.dev` | Cloudflare Tunnel → primary runtime | zWorkforce production HTTPS endpoint |
| `ha-a.zeaz.dev` | `192.168.74.134:9456` | VM-A direct API |
| `ha-b.zeaz.dev` | `192.168.74.135:9456` | VM-B direct API |
| `obs.zeaz.dev` | `192.168.74.134:19090` | Prometheus API |
| `studio.zeaz.dev` | Cloudflare Tunnel → loopback | ZSP Studio |
| `zarvis.zeaz.dev` | Cloudflare Tunnel → loopback | Z.A.R.V.I.S. gateway |
| `zider.zeaz.dev` | Cloudflare Tunnel → loopback | zider BFF |

## Terraform / DNS

The private A records are declared in `infrastructure/terraform/cloudflare/main.tf` and `zworkforce.tf`:

```hcl
resource "cloudflare_dns_record" "ha_a" {
  zone_id = var.cloudflare_zone_id
  name    = var.ha_a_hostname   # ha-a.zeaz.dev
  type    = "A"
  content = var.ha_a_ip         # 192.168.74.134
  ttl     = 1
  proxied = false               # private origin — NOT tunnel CNAME
}

resource "cloudflare_dns_record" "ha_b" { ... }
resource "cloudflare_dns_record" "obs"  { ... }
```

These records are **not** part of the Cloudflare Tunnel ingress. They resolve only inside the trusted private network.

## Deployment

Each VM runs an independent Docker Compose stack from `deploy/ha/`:

- `compose.vm-a.yaml` — deployed on VM-A
- `compose.vm-b.yaml` — deployed on VM-B

Shared environment template: `deploy/ha/compose.shared.env.example`

Both stacks point to the same Supabase PostgreSQL DSN and S3-compatible artifact backend.

## Observability

The observability stack on VM-B (`deploy/observability/compose.vm-b.yaml`) scrapes:

- `zworkforce-vm-a` → `192.168.74.134:9456/metrics` (bearer-authenticated)
- `zworkforce-vm-b` → `192.168.74.135:9456/metrics` (bearer-authenticated)
- `otel-collector` → internal OTLP metrics

Alertmanager is configured with a test webhook receiver for release evidence.

## Stage E verification

`scripts/release/verify-ha.sh` proves:

1. Both VMs are reachable via SSH.
2. Both VMs run `serve`, `worker`, `scheduler`, `outbox`.
3. API `/health` returns 200 on both VMs.
4. `ZWORKFORCE_INSTANCE_ID` differs between VMs (no identity collision).
5. Scheduler lease connectivity verified via shared Supabase DB.
6. Outbox ownership queryable per VM.
7. `/metrics` exports expected series on both VMs.

## Stage G verification

`scripts/release/verify-observability.sh` proves:

1. Prometheus targets `up` for `zworkforce-vm-a`, `zworkforce-vm-b`, `otel-collector`.
2. Metrics query returns series from both runtimes.
3. Alertmanager HTTP API ready.
4. Synthetic alert delivery attempted to configured webhook.
5. OTel Collector metrics endpoint reachable.

## GitHub Environment secrets

Create a protected GitHub Environment named `production` and set these secrets:

| Secret | Purpose |
| --- | --- |
| `SUPABASE_DATABASE_URL` | TLS Supabase Postgres connection string (shared by both VMs) |
| `ZWORKFORCE_API_KEYS` | zWorkforce API key(s) |
| `ZWORKFORCE_PROVIDER_API_KEY` | LLM provider API key |
| `ZWORKFORCE_METRICS_BEARER` | bearer token for `/metrics` |
| `ZWORKFORCE_OUTBOX_SIGNING_SECRET` | outbox webhook signing secret |
| `AWS_ACCESS_KEY_ID` | Supabase Storage S3 access key |
| `AWS_SECRET_ACCESS_KEY` | Supabase Storage S3 secret |
| `ALERTMANAGER_WEBHOOK_URL` | operator webhook for release evidence |
| `CLOUDFLARE_API_TOKEN` | scoped DNS/Tunnel API token |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| `CLOUDFLARE_ZONE_ID` | `zeaz.dev` zone ID |
| `CLOUDFLARE_TUNNEL_ID` | existing tunnel UUID |
| `CLOUDFLARE_TF_STATE_BUCKET` | private R2 Terraform-state bucket |
| `CLOUDFLARE_R2_S3_ENDPOINT` | R2 S3 API endpoint |
| `CLOUDFLARE_R2_ACCESS_KEY_ID` | bucket-scoped state key |
| `CLOUDFLARE_R2_SECRET_ACCESS_KEY` | bucket-scoped state secret |

## Constraints

- **Do not point `ha-b.zeaz.dev` at Supabase.** It must resolve to VM-B's zWorkforce API runtime.
- **Do not place `ha-a`, `ha-b`, `obs` in the Cloudflare Tunnel ingress.** They are private A records for internal operator access and observability only.
- **Runtime HA is not achieved by making Supabase an HTTP origin.** The secondary pool must be another zWorkforce runtime implementing the same API and health contract.
