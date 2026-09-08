######################################################################
# zomega — Multi-Tenant Agents & Billable Skills Platform
# Exposes the zomega API & runtime at zomega.zeaz.dev through Cloudflare
######################################################################

# ──────────────────────────────────────────────────────────────────── #
# Feature flag                                                         #
# ──────────────────────────────────────────────────────────────────── #
variable "enable_zomega" {
  type        = bool
  default     = true
  description = "Create zomega DNS record and include its ingress route in the Cloudflare Tunnel configuration."
}

# ──────────────────────────────────────────────────────────────────── #
# Hostnames                                                            #
# ──────────────────────────────────────────────────────────────────── #
variable "zomega_hostname" {
  type        = string
  default     = "zomega.zeaz.dev"
  description = "Public hostname for the zomega Agents & Skills platform."

  validation {
    condition     = endswith(lower(var.zomega_hostname), ".${lower(var.zone_name)}")
    error_message = "zomega_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

# ──────────────────────────────────────────────────────────────────── #
# Origin (loopback port 8000 published by zomega-api docker container)  #
# ──────────────────────────────────────────────────────────────────── #
variable "zomega_origin" {
  type        = string
  default     = "http://127.0.0.1:8000"
  description = "Loopback origin of the zomega backend reached by cloudflared."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zomega_origin))
    error_message = "zomega_origin must be a loopback http://127.0.0.1:<port> address."
  }
}

# ──────────────────────────────────────────────────────────────────── #
# Tunnel ingress (merged into main.tf local.all_service_ingress)       #
# ──────────────────────────────────────────────────────────────────── #
locals {
  zomega_ingress = var.enable_zomega ? [
    { hostname = var.zomega_hostname, service = var.zomega_origin },
  ] : []
}

# ──────────────────────────────────────────────────────────────────── #
# DNS                                                                  #
# ──────────────────────────────────────────────────────────────────── #
resource "cloudflare_dns_record" "zomega" {
  count   = var.enable_zomega ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = var.zomega_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zomega Agents and Skills platform via Cloudflare Tunnel"
}

# ──────────────────────────────────────────────────────────────────── #
# Outputs                                                              #
# ──────────────────────────────────────────────────────────────────── #
output "zomega_url" {
  value       = "https://${var.zomega_hostname}"
  description = "Public zomega URL."
}

output "zomega_ready_url" {
  value       = "https://${var.zomega_hostname}/health/ready"
  description = "zomega ready healthcheck URL."
}
