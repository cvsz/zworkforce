variable "zany_hostname" {
  type        = string
  default     = "zany.zeaz.dev"
  description = "Protected hostname for the zanything Universal AI Operator."

  validation {
    condition     = endswith(lower(var.zany_hostname), ".${lower(var.zone_name)}")
    error_message = "zany_hostname must be a subdomain of zone_name."
  }
}

variable "zany_origin" {
  type        = string
  default     = "http://127.0.0.1:8088"
  description = "Loopback origin published by the zanything Universal AI Operator container."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zany_origin))
    error_message = "zany_origin must use a loopback address."
  }
}

variable "zany_access_allowed_emails" {
  type        = set(string)
  default     = []
  description = "Exact operator emails allowed through Cloudflare Access for zanything. Empty inherits piewdash_access_allowed_emails."

  validation {
    condition = alltrue([
      for email in var.zany_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", lower(email)))
    ])
    error_message = "zany_access_allowed_emails must contain only valid operator emails."
  }
}

locals {
  zany_access_allowed_emails = length(var.zany_access_allowed_emails) > 0 ? var.zany_access_allowed_emails : var.piewdash_access_allowed_emails
}

resource "cloudflare_dns_record" "zany" {
  zone_id = var.cloudflare_zone_id
  name    = var.zany_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "Protected zanything Universal AI Operator via Cloudflare Tunnel"
}

resource "cloudflare_zero_trust_access_application" "zany" {
  account_id                 = var.cloudflare_account_id
  name                       = "zanything Universal AI Operator"
  domain                     = var.zany_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved zanything operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(local.zany_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

output "zany_url" {
  value       = "https://${var.zany_hostname}"
  description = "Protected zanything Universal AI Operator URL after DNS, tunnel ingress, and Cloudflare Access are active."
}

output "zany_access_audience" {
  value       = cloudflare_zero_trust_access_application.zany.aud
  description = "Audience claim expected on Cloudflare Access JWTs for zanything."
}
