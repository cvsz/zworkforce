variable "zslog_hostname" {
  type        = string
  default     = "zslog.zeaz.dev"
  description = "Public hostname for the zslog fake-credit realtime simulator & telemetry console."

  validation {
    condition     = endswith(lower(var.zslog_hostname), ".${lower(var.zone_name)}")
    error_message = "zslog_hostname must be a subdomain of zone_name."
  }
}

variable "zslog_origin" {
  type        = string
  default     = "http://127.0.0.1:9581"
  description = "Loopback origin published by the zslog systemd service."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zslog_origin))
    error_message = "zslog_origin must use a loopback address."
  }
}

resource "cloudflare_dns_record" "zslog" {
  zone_id = var.cloudflare_zone_id
  name    = var.zslog_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zslog synthetic telemetry console via Cloudflare Tunnel"
}

output "zslog_url" {
  value       = "https://${var.zslog_hostname}"
  description = "Public zslog telemetry console URL after DNS and tunnel ingress are active."
}
