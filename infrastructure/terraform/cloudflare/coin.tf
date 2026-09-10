######################################################################
# zCoin — CoinFlip Evidence Auditor
# Public hostname: zcoin.zeaz.dev
# Origin: loopback-only Nginx gateway on 127.0.0.1:18082
# Edge: Cloudflare Access (exact operator-email allowlist) + Tunnel
# Repository ownership: application code in cvsz/zcoin; edge config
# in cvsz/zworkforce (this file).
######################################################################

variable "coin_hostname" {
  type        = string
  default     = "zcoin.zeaz.dev"
  description = "Public hostname for the zCoin Evidence Auditor."

  validation {
    condition     = endswith(lower(var.coin_hostname), ".${lower(var.zone_name)}")
    error_message = "coin_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

variable "coin_origin" {
  type        = string
  default     = "http://127.0.0.1:18082"
  description = "Loopback origin for the zCoin production gateway (Nginx on 18082). Never reuse 18080 which is reserved by zDash."

  validation {
    condition     = var.coin_origin == "http://127.0.0.1:18082"
    error_message = "coin_origin must be http://127.0.0.1:18082 (zCoin is isolated from zDash)."
  }
}

variable "coin_access_allowed_emails" {
  type        = set(string)
  default     = []
  description = "Exact operator emails allowed through Cloudflare Access for zCoin. Empty inherits piewdash_access_allowed_emails."

  validation {
    condition = alltrue([
      for email in var.coin_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", lower(email)))
    ])
    error_message = "coin_access_allowed_emails must contain only valid operator emails."
  }
}

locals {
  coin_access_allowed_emails = length(var.coin_access_allowed_emails) > 0 ? var.coin_access_allowed_emails : var.piewdash_access_allowed_emails

  coin_ingress = [
    { hostname = var.coin_hostname, service = var.coin_origin },
  ]
}

resource "cloudflare_dns_record" "coin" {
  zone_id = var.cloudflare_zone_id
  name    = var.coin_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zCoin Evidence Auditor via Cloudflare Tunnel"
}

resource "cloudflare_zero_trust_access_application" "coin" {
  account_id                 = var.cloudflare_account_id
  name                       = "zCoin Evidence Auditor"
  domain                     = var.coin_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zCoin operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(local.coin_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

output "coin_url" {
  value       = "https://${var.coin_hostname}"
  description = "Protected zCoin URL after DNS, tunnel ingress, and Cloudflare Access are active."
}

output "coin_access_audience" {
  value       = cloudflare_zero_trust_access_application.coin.aud
  description = "Audience claim expected on Cloudflare Access JWTs for zCoin."
}
