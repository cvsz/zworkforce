######################################################################
# ZSME — Thailand-first SME accounting & business finance platform
# Public hostnames: zsme.zeaz.dev, ai-dbc.zeaz.dev, prod.zeaz.dev
# Origin: loopback-only ZSME API gateway on 127.0.0.1:18081.
# NOTE: 18081 is owned by the ZSME API gateway (cvsz/zsme compose maps
# 18081 -> api:8000). zeaz-one.tf also defaults its origin to 18081, so
# keep enable_zeaz_one = false while ZSME is live, or move ZEAZ One first.
# Edge: Cloudflare Access (exact operator-email allowlist) + Tunnel.
# Repository ownership: application code in cvsz/zsme; edge config
# in cvsz/zworkforce (this file).
######################################################################

variable "zsme_hostname" {
  type        = string
  default     = "zsme.zeaz.dev"
  description = "Public hostname for the ZSME accounting platform web UI."

  validation {
    condition     = endswith(lower(var.zsme_hostname), ".${lower(var.zone_name)}")
    error_message = "zsme_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

variable "zsme_origin" {
  type        = string
  default     = "http://127.0.0.1:18081"
  description = "Loopback-only ZSME API gateway reached by cloudflared."

  validation {
    condition     = var.zsme_origin == "http://127.0.0.1:18081"
    error_message = "zsme_origin must use the reviewed ZSME API gateway at http://127.0.0.1:18081."
  }
}

variable "ai_dbc_hostname" {
  type        = string
  default     = "ai-dbc.zeaz.dev"
  description = "Public hostname for the ZSME AI document & business control assistant."

  validation {
    condition     = endswith(lower(var.ai_dbc_hostname), ".${lower(var.zone_name)}")
    error_message = "ai_dbc_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

variable "ai_dbc_origin" {
  type        = string
  default     = "http://127.0.0.1:18081"
  description = "Loopback-only ZSME AI DBC origin reached by cloudflared. Shares the ZSME API gateway."

  validation {
    condition     = var.ai_dbc_origin == "http://127.0.0.1:18081"
    error_message = "ai_dbc_origin must use the reviewed ZSME API gateway at http://127.0.0.1:18081."
  }
}

variable "prod_hostname" {
  type        = string
  default     = "prod.zeaz.dev"
  description = "Public hostname for the ZSME production control surface."

  validation {
    condition     = endswith(lower(var.prod_hostname), ".${lower(var.zone_name)}")
    error_message = "prod_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

variable "prod_origin" {
  type        = string
  default     = "http://127.0.0.1:18081"
  description = "Loopback-only ZSME production origin reached by cloudflared. Shares the ZSME API gateway."

  validation {
    condition     = var.prod_origin == "http://127.0.0.1:18081"
    error_message = "prod_origin must use the reviewed ZSME API gateway at http://127.0.0.1:18081."
  }
}

variable "zsme_access_allowed_emails" {
  type        = set(string)
  default     = []
  description = "Exact operator emails allowed through Cloudflare Access for ZSME. Empty inherits piewdash_access_allowed_emails."

  validation {
    condition = alltrue([
      for email in var.zsme_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", lower(email)))
    ])
    error_message = "zsme_access_allowed_emails must contain only valid operator emails."
  }
}

# Renamed aidualbc_* -> ai_dbc_* for readability. The moved block keeps the
# live DNS record in state so no DNS recreation happens on apply.
moved {
  from = cloudflare_dns_record.aidualbc
  to   = cloudflare_dns_record.ai_dbc
}

locals {
  zsme_access_allowed_emails = length(var.zsme_access_allowed_emails) > 0 ? var.zsme_access_allowed_emails : var.piewdash_access_allowed_emails

  # Canonical ZSME-family ingress. Keeping the host/origin pairs next to the
  # DNS declarations prevents the managed tunnel configuration and the
  # cloudflared_ingress output from silently diverging.
  zsme_ingress = [
    { hostname = var.zsme_hostname, service = var.zsme_origin },
    { hostname = var.ai_dbc_hostname, service = var.ai_dbc_origin },
    { hostname = var.prod_hostname, service = var.prod_origin },
  ]
}

resource "cloudflare_dns_record" "zsme" {
  zone_id = var.cloudflare_zone_id
  name    = var.zsme_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZSME accounting platform web UI via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "ai_dbc" {
  zone_id = var.cloudflare_zone_id
  name    = var.ai_dbc_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZSME AI document & business control assistant via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "prod" {
  zone_id = var.cloudflare_zone_id
  name    = var.prod_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZSME production control surface via Cloudflare Tunnel"
}

resource "cloudflare_zero_trust_access_application" "zsme" {
  account_id                 = var.cloudflare_account_id
  name                       = "ZSME Accounting Platform"
  domain                     = var.zsme_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved ZSME operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(local.zsme_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

resource "cloudflare_zero_trust_access_application" "ai_dbc" {
  account_id                 = var.cloudflare_account_id
  name                       = "ZSME AI Document & Business Control"
  domain                     = var.ai_dbc_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved ZSME operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(local.zsme_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

resource "cloudflare_zero_trust_access_application" "prod" {
  account_id                 = var.cloudflare_account_id
  name                       = "ZSME Production Control Surface"
  domain                     = var.prod_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved ZSME operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(local.zsme_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

output "zsme_url" {
  value       = "https://${var.zsme_hostname}"
  description = "Protected ZSME accounting platform URL after DNS, tunnel ingress, and Cloudflare Access are active."
}

output "zsme_access_audience" {
  value       = cloudflare_zero_trust_access_application.zsme.aud
  description = "Audience claim expected on Cloudflare Access JWTs for ZSME."
}

output "ai_dbc_url" {
  value       = "https://${var.ai_dbc_hostname}"
  description = "Protected ZSME AI document & business control URL after DNS, tunnel ingress, and Cloudflare Access are active."
}

output "ai_dbc_access_audience" {
  value       = cloudflare_zero_trust_access_application.ai_dbc.aud
  description = "Audience claim expected on Cloudflare Access JWTs for ZSME AI DBC."
}

output "prod_url" {
  value       = "https://${var.prod_hostname}"
  description = "Protected ZSME production control surface URL after DNS, tunnel ingress, and Cloudflare Access are active."
}

output "prod_access_audience" {
  value       = cloudflare_zero_trust_access_application.prod.aud
  description = "Audience claim expected on Cloudflare Access JWTs for ZSME production."
}
