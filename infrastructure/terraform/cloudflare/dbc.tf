variable "dbc_hostname" {
  type        = string
  default     = "dbc.zeaz.dev"
  description = "Public hostname for the QwenDBC full-stack application."

  validation {
    condition     = endswith(lower(var.dbc_hostname), ".${lower(var.zone_name)}")
    error_message = "dbc_hostname must be a subdomain of zone_name."
  }
}

variable "dbc_origin" {
  type        = string
  default     = "http://127.0.0.1:3100"
  description = "Loopback frontend origin for the QwenDBC Docker Compose stack."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.dbc_origin))
    error_message = "dbc_origin must use a loopback HTTP address."
  }
}

locals {
  qwendbc_ingress = [
    { hostname = var.dbc_hostname, service = var.dbc_origin }
  ]
}

resource "cloudflare_dns_record" "dbc" {
  zone_id = var.cloudflare_zone_id
  name    = var.dbc_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "QwenDBC full-stack application via Cloudflare Tunnel"
}

output "dbc_url" {
  value       = "https://${var.dbc_hostname}"
  description = "Public QwenDBC URL."
}
