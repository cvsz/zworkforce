# ==============================================================================
# zksato — Risk-first SET/TFEX + USDT paper trading control plane
# Public hostnames: zksato.zeaz.dev (frontend), zksato-api.zeaz.dev (api),
#                   zksato-dash.zeaz.dev (dashboard)
# Optional alias hostnames: zksato.zeaz.dev, zksato-api.zeaz.dev,
#                           zksato-dash.zeaz.dev
# Origins are loopback-only and reached by cloudflared on the host.
# ==============================================================================
variable "zksato_hostname" {
  type        = string
  default     = "zksato.zeaz.dev"
  description = "Public hostname for zksato frontend (Next.js)."

  validation {
    condition     = endswith(lower(var.zksato_hostname), ".${lower(var.zone_name)}")
    error_message = "zksato_hostname must be a subdomain of zone_name."
  }
}

variable "zksato_origin" {
  type        = string
  default     = "http://127.0.0.1:3016"
  description = "Loopback origin for zksato frontend (Next.js on 3016)."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zksato_origin))
    error_message = "zksato_origin must use a loopback address."
  }
}

variable "zksato_api_hostname" {
  type        = string
  default     = "zksato-api.zeaz.dev"
  description = "Public hostname for zksato API (FastAPI on 9569)."

  validation {
    condition     = endswith(lower(var.zksato_api_hostname), ".${lower(var.zone_name)}")
    error_message = "zksato_api_hostname must be a subdomain of zone_name."
  }
}

variable "zksato_api_origin" {
  type        = string
  default     = "http://127.0.0.1:9569"
  description = "Loopback origin for zksato API."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zksato_api_origin))
    error_message = "zksato_api_origin must use a loopback address."
  }
}

variable "zksato_dash_hostname" {
  type        = string
  default     = "zksato-dash.zeaz.dev"
  description = "Public hostname for zksato dashboard (Vite/nginx on 5174)."

  validation {
    condition     = endswith(lower(var.zksato_dash_hostname), ".${lower(var.zone_name)}")
    error_message = "zksato_dash_hostname must be a subdomain of zone_name."
  }
}

variable "zksato_dash_origin" {
  type        = string
  default     = "http://127.0.0.1:5174"
  description = "Loopback origin for zksato dashboard."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zksato_dash_origin))
    error_message = "zksato_dash_origin must use a loopback address."
  }
}

variable "zksato_alias_enabled" {
  type        = bool
  default     = false
  description = "Enable the optional zksato.zeaz.dev frontend/API/dashboard alias. Keep false until the zeaz.dev zone is verified and its records are approved."
}

variable "zksato_alias_zone_id" {
  type        = string
  default     = ""
  nullable    = false
  description = "Cloudflare zone ID for zeaz.dev. Required only when zksato_alias_enabled is true; never put the API token here."

  validation {
    condition     = var.zksato_alias_zone_id == "" || can(regex("^[0-9a-f]{32}$", lower(var.zksato_alias_zone_id)))
    error_message = "zksato_alias_zone_id must be empty or a 32-character hexadecimal Cloudflare zone ID."
  }
}

variable "zksato_alias_hostname" {
  type        = string
  default     = "zksato.zeaz.dev"
  description = "Verified frontend alias hostname in the zeaz.dev zone."

  validation {
    condition     = lower(var.zksato_alias_hostname) == "zksato.zeaz.dev"
    error_message = "zksato_alias_hostname must be exactly zksato.zeaz.dev."
  }
}

variable "zksato_alias_api_hostname" {
  type        = string
  default     = "zksato-api.zeaz.dev"
  description = "API alias hostname in the zeaz.dev zone."

  validation {
    condition     = lower(var.zksato_alias_api_hostname) == "zksato-api.zeaz.dev"
    error_message = "zksato_alias_api_hostname must be exactly zksato-api.zeaz.dev."
  }
}

variable "zksato_alias_dash_hostname" {
  type        = string
  default     = "zksato-dash.zeaz.dev"
  description = "Dashboard alias hostname in the zeaz.dev zone."

  validation {
    condition     = lower(var.zksato_alias_dash_hostname) == "zksato-dash.zeaz.dev"
    error_message = "zksato_alias_dash_hostname must be exactly zksato-dash.zeaz.dev."
  }
}

variable "zksato_access_allowed_emails" {
  type        = set(string)
  default     = []
  description = "Exact operator emails allowed via Cloudflare Access for zksato. Empty means no Access (public) – set for protected deployments."

  validation {
    condition = alltrue([
      for email in var.zksato_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", lower(email)))
    ])
    error_message = "zksato_access_allowed_emails must contain only valid emails."
  }
}

locals {
  zksato_primary_ingress = [
    { hostname = var.zksato_hostname, service = var.zksato_origin },
    { hostname = var.zksato_api_hostname, service = var.zksato_api_origin },
    { hostname = var.zksato_dash_hostname, service = var.zksato_dash_origin },
  ]

  zksato_alias_ingress = var.zksato_alias_enabled ? [
    { hostname = var.zksato_alias_hostname, service = var.zksato_origin },
    { hostname = var.zksato_alias_api_hostname, service = var.zksato_api_origin },
    { hostname = var.zksato_alias_dash_hostname, service = var.zksato_dash_origin },
  ] : []

  zksato_ingress = concat(local.zksato_primary_ingress, local.zksato_alias_ingress)
}

resource "terraform_data" "zksato_alias_contract" {
  count = var.zksato_alias_enabled ? 1 : 0

  input = {
    zone_name    = "zeaz.dev"
    zone_id      = var.zksato_alias_zone_id
    frontend     = var.zksato_alias_hostname
    api          = var.zksato_alias_api_hostname
    dashboard    = var.zksato_alias_dash_hostname
    tunnel_cname = local.tunnel_cname
  }

  lifecycle {
    precondition {
      condition     = length(trimspace(var.zksato_alias_zone_id)) == 32
      error_message = "zksato_alias_enabled requires the verified Cloudflare zone ID for zeaz.dev."
    }
  }
}

resource "cloudflare_dns_record" "zksato" {
  zone_id = var.cloudflare_zone_id
  name    = var.zksato_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zksato frontend via Cloudflare Tunnel (Next.js USDT-first paper)"
}

resource "cloudflare_dns_record" "zksato_api" {
  zone_id = var.cloudflare_zone_id
  name    = var.zksato_api_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zksato API via Cloudflare Tunnel (FastAPI paper mode)"
}

resource "cloudflare_dns_record" "zksato_dash" {
  zone_id = var.cloudflare_zone_id
  name    = var.zksato_dash_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zksato dashboard via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zksato_alias" {
  count   = var.zksato_alias_enabled ? 1 : 0
  zone_id = var.zksato_alias_zone_id
  name    = var.zksato_alias_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zksato frontend alias via Cloudflare Tunnel (zeaz.dev)"
}

resource "cloudflare_dns_record" "zksato_alias_api" {
  count   = var.zksato_alias_enabled ? 1 : 0
  zone_id = var.zksato_alias_zone_id
  name    = var.zksato_alias_api_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zksato API alias via Cloudflare Tunnel (zeaz.dev)"
}

resource "cloudflare_dns_record" "zksato_alias_dash" {
  count   = var.zksato_alias_enabled ? 1 : 0
  zone_id = var.zksato_alias_zone_id
  name    = var.zksato_alias_dash_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zksato dashboard alias via Cloudflare Tunnel (zeaz.dev)"
}

# Optional Access protection — created only when allow-list is non-empty.
resource "cloudflare_zero_trust_access_application" "zksato" {
  count                      = length(var.zksato_access_allowed_emails) > 0 ? 1 : 0
  account_id                 = var.cloudflare_account_id
  name                       = "zksato Trading Control Plane"
  domain                     = var.zksato_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zksato operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(var.zksato_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

resource "cloudflare_zero_trust_access_application" "zksato_api" {
  count                      = length(var.zksato_access_allowed_emails) > 0 ? 1 : 0
  account_id                 = var.cloudflare_account_id
  name                       = "zksato API"
  domain                     = var.zksato_api_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zksato operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(var.zksato_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

resource "cloudflare_zero_trust_access_application" "zksato_alias" {
  count                      = var.zksato_alias_enabled && length(var.zksato_access_allowed_emails) > 0 ? 1 : 0
  account_id                 = var.cloudflare_account_id
  name                       = "zksato Trading Control Plane (zeaz.dev)"
  domain                     = var.zksato_alias_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zksato operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(var.zksato_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

resource "cloudflare_zero_trust_access_application" "zksato_alias_api" {
  count                      = var.zksato_alias_enabled && length(var.zksato_access_allowed_emails) > 0 ? 1 : 0
  account_id                 = var.cloudflare_account_id
  name                       = "zksato API (zeaz.dev)"
  domain                     = var.zksato_alias_api_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zksato operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(var.zksato_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

resource "cloudflare_zero_trust_access_application" "zksato_alias_dash" {
  count                      = var.zksato_alias_enabled && length(var.zksato_access_allowed_emails) > 0 ? 1 : 0
  account_id                 = var.cloudflare_account_id
  name                       = "zksato dashboard (zeaz.dev)"
  domain                     = var.zksato_alias_dash_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zksato operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(var.zksato_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

output "zksato_url" {
  value       = "https://${var.zksato_hostname}"
  description = "Public zksato frontend URL."
}

output "zksato_api_url" {
  value       = "https://${var.zksato_api_hostname}"
  description = "Public zksato API URL."
}

output "zksato_dash_url" {
  value       = "https://${var.zksato_dash_hostname}"
  description = "Public zksato dashboard URL."
}

output "zksato_alias_urls" {
  value = var.zksato_alias_enabled ? {
    frontend  = "https://${var.zksato_alias_hostname}"
    api       = "https://${var.zksato_alias_api_hostname}"
    dashboard = "https://${var.zksato_alias_dash_hostname}"
  } : {}
  description = "Optional zeaz.dev zksato URLs; empty until the alias contract is enabled with a verified zone ID."
}
