######################################################################
# ZASI — Omniversal Superintelligence J.A.R.V.I.S. Cockpit
# Exposes the ZASI backend (REST + WebSocket + static SPA) at
# zasi.zeaz.dev through the existing Cloudflare Tunnel.
######################################################################

# ──────────────────────────────────────────────────────────────────── #
# Feature flag                                                         #
# ──────────────────────────────────────────────────────────────────── #
variable "enable_zasi" {
  type        = bool
  default     = false
  description = "Create ZASI DNS record and include its ingress route in the Cloudflare Tunnel configuration."
}

# ──────────────────────────────────────────────────────────────────── #
# Hostnames                                                            #
# ──────────────────────────────────────────────────────────────────── #
variable "zasi_hostname" {
  type        = string
  default     = "zasi.zeaz.dev"
  description = "Public hostname for the ZASI J.A.R.V.I.S. cockpit."

  validation {
    condition     = endswith(lower(var.zasi_hostname), ".${lower(var.zone_name)}")
    error_message = "zasi_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

# ──────────────────────────────────────────────────────────────────── #
# Origin (loopback — server hardened to 127.0.0.1 after pentest)      #
# ──────────────────────────────────────────────────────────────────── #
variable "zasi_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Loopback origin of the ZASI backend reached by cloudflared. Must remain on 127.0.0.1 (pentest requirement)."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zasi_origin))
    error_message = "zasi_origin must be a loopback http://127.0.0.1:<port> address."
  }
}

# ──────────────────────────────────────────────────────────────────── #
# Tunnel ingress (merged into main.tf local.all_service_ingress)       #
# ──────────────────────────────────────────────────────────────────── #
locals {
  zasi_ingress = var.enable_zasi ? [
    { hostname = var.zasi_hostname, service = var.zasi_origin },
  ] : []
}

# ──────────────────────────────────────────────────────────────────── #
# DNS                                                                  #
# ──────────────────────────────────────────────────────────────────── #
resource "cloudflare_dns_record" "zasi" {
  count   = var.enable_zasi ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = var.zasi_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZASI J.A.R.V.I.S. Omniversal Superintelligence cockpit via Cloudflare Tunnel"
}

# ──────────────────────────────────────────────────────────────────── #
# Outputs                                                              #
# ──────────────────────────────────────────────────────────────────── #
output "zasi_url" {
  value       = "https://${var.zasi_hostname}"
  description = "Public ZASI J.A.R.V.I.S. cockpit URL."
}

output "zasi_api_url" {
  value       = "https://${var.zasi_hostname}/api/status"
  description = "ZASI REST API health check URL."
}

output "zasi_ws_url" {
  value       = "wss://${var.zasi_hostname}/ws"
  description = "ZASI WebSocket real-time push endpoint (RFC 6455, requires Cloudflare WebSockets enabled)."
}
