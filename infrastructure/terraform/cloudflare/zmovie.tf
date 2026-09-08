######################################################################
# zMovie — AI Movie Production Studio
# Exposes the zMovie production API and Studio at zmovie.zeaz.dev
# through the existing Cloudflare Tunnel.
######################################################################

variable "enable_zmovie" {
  type        = bool
  default     = false
  description = "Create the zMovie DNS record and include its ingress route in the Cloudflare Tunnel configuration."
}

variable "zmovie_hostname" {
  type        = string
  default     = "zmovie.zeaz.dev"
  description = "Public hostname for the zMovie production Studio."

  validation {
    condition     = endswith(lower(var.zmovie_hostname), ".${lower(var.zone_name)}")
    error_message = "zmovie_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

variable "zmovie_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Loopback zMovie origin reached by cloudflared."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zmovie_origin))
    error_message = "zmovie_origin must use a loopback http://127.0.0.1:<port> address."
  }
}

locals {
  zmovie_ingress = var.enable_zmovie ? [
    { hostname = var.zmovie_hostname, service = var.zmovie_origin },
  ] : []
}

resource "cloudflare_dns_record" "zmovie" {
  count   = var.enable_zmovie ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = var.zmovie_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zMovie AI Movie Production Studio via Cloudflare Tunnel"
}

output "zmovie_url" {
  value       = "https://${var.zmovie_hostname}"
  description = "Public zMovie production Studio URL."
}

output "zmovie_health_url" {
  value       = "https://${var.zmovie_hostname}/api/v2/health"
  description = "zMovie production API health endpoint."
}
