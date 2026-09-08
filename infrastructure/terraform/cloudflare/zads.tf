######################################################################
# ZADS — Zaffiliate Advertising & Distribution Service
# Exposes the ZADS backend at zads.zeaz.dev through the existing
# Cloudflare Tunnel.
######################################################################

# ──────────────────────────────────────────────────────────────────── #
# Feature flag                                                         #
# ──────────────────────────────────────────────────────────────────── #
variable "enable_zads" {
  type        = bool
  default     = false
  description = "Create ZADS DNS record and include its ingress route in the Cloudflare Tunnel configuration."
}

# ──────────────────────────────────────────────────────────────────── #
# Hostnames                                                            #
# ──────────────────────────────────────────────────────────────────── #
variable "zads_hostname" {
  type        = string
  default     = "zads.zeaz.dev"
  description = "Public hostname for the Zaffiliate Advertising & Distribution Service."

  validation {
    condition     = endswith(lower(var.zads_hostname), ".${lower(var.zone_name)}")
    error_message = "zads_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

# ──────────────────────────────────────────────────────────────────── #
# Origin (loopback — server hardened to 127.0.0.1 after pentest)      #
# ──────────────────────────────────────────────────────────────────── #
variable "zads_origin" {
  type        = string
  default     = "http://127.0.0.1:8081"
  description = "Loopback origin of the ZADS backend reached by cloudflared. Must remain on 127.0.0.1 (pentest requirement)."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zads_origin))
    error_message = "zads_origin must be a loopback http://127.0.0.1:<port> address."
  }
}

# ──────────────────────────────────────────────────────────────────── #
# Tunnel ingress (merged into main.tf local.all_service_ingress)       #
# ──────────────────────────────────────────────────────────────────── #
locals {
  zads_ingress = var.enable_zads ? [
    { hostname = var.zads_hostname, service = var.zads_origin },
  ] : []
}

# ──────────────────────────────────────────────────────────────────── #
# DNS                                                                  #
# ──────────────────────────────────────────────────────────────────── #
resource "cloudflare_dns_record" "zads" {
  count   = var.enable_zads ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = var.zads_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZADS Zaffiliate Advertising & Distribution Service via Cloudflare Tunnel"
}

# ──────────────────────────────────────────────────────────────────── #
# Outputs                                                              #
# ──────────────────────────────────────────────────────────────────── #
output "zads_url" {
  value       = "https://${var.zads_hostname}"
  description = "Public ZADS URL."
}

output "zads_api_url" {
  value       = "https://${var.zads_hostname}/api/v1/version"
  description = "ZADS REST API health check URL."
}
