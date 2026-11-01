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

output "dbc_url" {
  value       = "https://${var.dbc_hostname}"
  description = "Public QwenDBC URL after DNS and tunnel ingress are active."
}