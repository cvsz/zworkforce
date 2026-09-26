# zTTato — zttato.zeaz.dev

Status: **NOT STARTED.** This file records verified current state and the
decisions still required before any change. Nothing described under
"Proposed" has been applied.

## 1. Verified current state (2026-09-25)

| Item | Value |
|---|---|
| Public hostname | `zttato.zeaz.dev` |
| Responds | HTTP 401, `<title>zTTato Creator — Legal & Review Preview</title>` |
| DNS CNAME | `custom-domains.chatgpt.site`, proxied |
| Other records | one TXT `tiktok-developers-site-verification` — **preserve** |
| Managed by this Terraform stack | **No** (absent from `terraform state list`) |
| Tunnel `zttato-platform` | **does not exist** |
| Tunnels named `zttato*` | three, all **soft-deleted**, none with ingress config |
| Origin on this host | none: no systemd unit, no container, no listening port |

The hostname is live and served entirely by the ChatGPT custom domain. It is
not broken today, so any cutover is a deliberate service interruption.

## 2. Why the record is not in Terraform

The CNAME was created outside Terraform, so the stack has no record of it.
Declaring a new `cloudflare_dns_record` for the same name would fail with a
duplicate-record error, because the live record already exists. Adoption must
use `terraform import` before any modification.

## 3. Decisions required before starting

1. **Destination.** Follow the existing convention and publish on the shared
   tunnel (`local.tunnel_cname`), or create a separate `zttato-platform`
   tunnel. The convention is the shared tunnel; a separate tunnel needs its own
   credential handling.
2. **Origin port.** No zTTato service exists on this host. The port must be
   decided and the app deployed and healthy on loopback before the hostname is
   published. Do not guess it.
3. **ChatGPT custom domain.** Confirm whether the existing upstream is being
   replaced or kept as an internal dependency. If the ChatGPT backend is still
   called, its address must be configured in the app, not in DNS.

## 4. Proposed sequence

1. Deploy the zTTato app; verify `curl 127.0.0.1:<port>` answers locally.
2. Add `zttato_hostname` and `zttato_origin` variables, a
   `cloudflare_dns_record.zttato`, the ingress rule and the output, following
   the `zttshop` pattern. Validate the origin is loopback-only.
3. `terraform fmt -check -recursive` and `terraform validate`.
4. `terraform import` the **existing** record so DNS is never briefly absent.
5. Publish a canary hostname, confirm routing end to end.
6. Only then switch `zttato.zeaz.dev`. TTL is 1 and the record is proxied, so
   the switch is fast, but it is still an interruption.
7. Review the plan for zero unexpected destroys. The shared tunnel also serves
   production hostnames, so an ingress mistake affects more than zTTato.

## 5. Rollback

Restore the CNAME to `custom-domains.chatgpt.site` and remove the ingress rule.
The previous upstream is untouched, so recovery is a single DNS change. Do not
delete the TXT verification record.

## 6. Constraints

Keep blocked until separately approved: production reboot, destructive
Terraform operations, live database migrations, live payment capture, live
ticket sales and automatic public publication.
