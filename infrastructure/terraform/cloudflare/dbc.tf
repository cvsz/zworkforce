variable "dbc_hostname" {
  type        = string
  default     = "dbc.zeaz.dev"
  description = "Public hostname for the QwenDBC local-first chat and document retrieval app."

  validation {
    condition     = endswith(lower(var.dbc_hostname), ".${lower(var.zone_name)}")
    error_message = "dbc_hostname must be a subdomain of zone_name."
  }
}

variable "dbc_origin" {
  type        = string
  default     = "http://127.0.0.1:3002"
  description = "Loopback origin reached by cloudflared for the QwenDBC frontend. Uses 3002 to avoid colliding with OpenWebUI chat on 3000/3080. The frontend proxies /api/* to the backend on port 8000."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.dbc_origin))
    error_message = "dbc_origin must use a loopback address."
  }
}

resource "cloudflare_dns_record" "dbc" {
  zone_id = var.cloudflare_zone_id
  name    = var.dbc_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "QwenDBC chat interface via Cloudflare Tunnel"
}

resource "cloudflare_zero_trust_access_application" "dbc" {
  account_id                 = var.cloudflare_account_id
  name                       = "QwenDBC"
  domain                     = var.dbc_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved QwenDBC operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(var.piewdash_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

output "dbc_url" {
  value       = "https://${var.dbc_hostname}"
  description = "Public QwenDBC URL after DNS, tunnel ingress, and Cloudflare Access are active."
}

output "dbc_access_audience" {
  value       = cloudflare_zero_trust_access_application.dbc.aud
  description = "Audience claim expected on Cloudflare Access JWTs for QwenDBC."
}