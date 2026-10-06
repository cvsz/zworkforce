# CMe application ingress. zWorkforce owns the zeaz.dev edge contract;
# the CMe repository owns only the application listening behind this origin.

variable "cme_hostname" {
  type        = string
  default     = "cme.zeaz.dev"
  description = "Public hostname for the CMe application."

  validation {
    condition     = endswith(lower(var.cme_hostname), ".${lower(var.zone_name)}")
    error_message = "cme_hostname must be a subdomain of zone_name."
  }
}

variable "cme_origin" {
  type        = string
  default     = "http://127.0.0.1:8001"
  description = "Loopback origin published by the CMe application."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.cme_origin))
    error_message = "cme_origin must use a loopback address."
  }
}

resource "cloudflare_dns_record" "cme" {
  zone_id = var.cloudflare_zone_id
  name    = var.cme_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "CMe application via the zWorkforce-owned Cloudflare Tunnel"
}

output "cme_url" {
  value       = "https://${var.cme_hostname}"
  description = "Public CMe URL after DNS and tunnel routing are active."
}
