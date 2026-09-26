# ==============================================================================
# zkSato — USDT-first paper trading control plane (*.zeaz.dev)
# ==============================================================================
# Ported from the unmanaged copy in the `zeaz` repository, which declared only
# `zksato.zeaz.dev` and had never been applied. The deployed stack publishes
# three surfaces, matching the running containers:
#
#   zksato.zeaz.dev      -> 127.0.0.1:3016  zksato-frontend-1
#   zksato-api.zeaz.dev  -> 127.0.0.1:9569  zksato-api-1
#   zksato-dash.zeaz.dev -> 127.0.0.1:5174  zksato-dashboard-1
#
# The API reports execution_mode "paper" and live_trading_enabled false. Nothing
# here changes that; publishing the hostname does not authorise live trading.

variable "zksato_hostname" {
  type        = string
  default     = "zksato.zeaz.dev"
  description = "Public hostname for the zkSato frontend."

  validation {
    condition     = endswith(lower(var.zksato_hostname), ".${lower(var.zone_name)}")
    error_message = "zksato_hostname must be a subdomain of zone_name."
  }
}

variable "zksato_origin" {
  type        = string
  default     = "http://127.0.0.1:3016"
  description = "Loopback origin published by the zkSato frontend."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zksato_origin))
    error_message = "zksato_origin must use a loopback address."
  }
}

variable "zksato_api_hostname" {
  type        = string
  default     = "zksato-api.zeaz.dev"
  description = "Public API hostname for the zkSato trading control plane."

  validation {
    condition     = endswith(lower(var.zksato_api_hostname), ".${lower(var.zone_name)}")
    error_message = "zksato_api_hostname must be a subdomain of zone_name."
  }
}

variable "zksato_api_origin" {
  type        = string
  default     = "http://127.0.0.1:9569"
  description = "Loopback origin published by the zkSato API service."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zksato_api_origin))
    error_message = "zksato_api_origin must use a loopback address."
  }
}

variable "zksato_dash_hostname" {
  type        = string
  default     = "zksato-dash.zeaz.dev"
  description = "Public dashboard hostname for zkSato."

  validation {
    condition     = endswith(lower(var.zksato_dash_hostname), ".${lower(var.zone_name)}")
    error_message = "zksato_dash_hostname must be a subdomain of zone_name."
  }
}

variable "zksato_dash_origin" {
  type        = string
  default     = "http://127.0.0.1:5174"
  description = "Loopback origin published by the zkSato dashboard."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zksato_dash_origin))
    error_message = "zksato_dash_origin must use a loopback address."
  }
}

variable "zksato_access_allowed_emails" {
  type        = list(string)
  default     = []
  description = "Operator emails allowed through Cloudflare Access when the alias is enabled. Empty inherits piewdash_access_allowed_emails."

  validation {
    condition = alltrue([
      for email in var.zksato_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", email))
    ])
    error_message = "zksato_access_allowed_emails must contain only valid operator emails."
  }
}

variable "zksato_alias_enabled" {
  type        = bool
  default     = false
  description = "Create the Cloudflare Access alias for zkSato. Off by default so publishing the hostnames does not add an access policy that nobody has approved."
}

locals {
  zksato_access_allowed_emails = length(var.zksato_access_allowed_emails) > 0 ? var.zksato_access_allowed_emails : var.piewdash_access_allowed_emails
}

resource "cloudflare_dns_record" "zksato" {
  zone_id = var.cloudflare_zone_id
  name    = var.zksato_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zkSato frontend via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zksato_api" {
  zone_id = var.cloudflare_zone_id
  name    = var.zksato_api_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zkSato API via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zksato_dash" {
  zone_id = var.cloudflare_zone_id
  name    = var.zksato_dash_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zkSato dashboard via Cloudflare Tunnel"
}

resource "cloudflare_zero_trust_access_application" "zksato" {
  count = var.zksato_alias_enabled ? 1 : 0

  account_id                 = var.cloudflare_account_id
  name                       = "zkSato Trading Control Plane"
  domain                     = var.zksato_api_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zkSato operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(local.zksato_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

output "zksato_url" {
  value       = "https://${var.zksato_hostname}"
  description = "Public zkSato frontend URL after the proxied DNS record and tunnel ingress are active."
}

output "zksato_api_url" {
  value       = "https://${var.zksato_api_hostname}"
  description = "Public zkSato API URL after the proxied DNS record and tunnel ingress are active."
}

output "zksato_dash_url" {
  value       = "https://${var.zksato_dash_hostname}"
  description = "Public zkSato dashboard URL after the proxied DNS record and tunnel ingress are active."
}
