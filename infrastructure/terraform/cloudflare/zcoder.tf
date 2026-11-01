# ==============================================================================
# ZCoder — AI Coding Assistant & FastAPI Backend Gateway (*.zeaz.dev)
# ==============================================================================
# Public hostname: zcoder.zeaz.dev
# Ingress routes:
#   - https://zcoder.zeaz.dev/api/* -> http://192.168.1.85:8088 (ZCoder API backend)
#   - https://zcoder.zeaz.dev/*     -> http://192.168.1.85:8420 (ZCoder WebApp)
# Edge: Cloudflare Tunnel (CNAME proxied to Cloudflare Tunnel)
# ==============================================================================

variable "zcoder_hostname" {
  type        = string
  default     = "zcoder.zeaz.dev"
  description = "Public hostname for the ZCoder coding assistant and API gateway."

  validation {
    condition     = endswith(lower(var.zcoder_hostname), ".${lower(var.zone_name)}")
    error_message = "zcoder_hostname must be a subdomain of zone_name."
  }
}

variable "zcoder_origin" {
  type        = string
  default     = "http://192.168.1.85:8420"
  description = "Origin reached by cloudflared for the ZCoder WebApp (default: port 8420)."

  validation {
    condition     = can(regex("^https?://[a-zA-Z0-9.-]+(:[0-9]+)?$", var.zcoder_origin))
    error_message = "zcoder_origin must use a valid HTTP or HTTPS origin with an optional port."
  }
}

variable "zcoder_api_origin" {
  type        = string
  default     = "http://192.168.1.85:8088"
  description = "Origin reached by cloudflared for the ZCoder FastAPI backend API server (default: port 8088)."

  validation {
    condition     = can(regex("^https?://[a-zA-Z0-9.-]+(:[0-9]+)?$", var.zcoder_api_origin))
    error_message = "zcoder_api_origin must use a valid HTTP or HTTPS origin with an optional port."
  }
}

resource "cloudflare_dns_record" "zcoder" {
  zone_id = var.cloudflare_zone_id
  name    = var.zcoder_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZCoder server via Cloudflare Tunnel"
}

locals {
  zcoder_ingress = [
    {
      hostname = var.zcoder_hostname
      path     = "^/api(/.*)?$"
      service  = var.zcoder_api_origin
    },
    {
      hostname = var.zcoder_hostname
      service  = var.zcoder_origin
    },
  ]
}

output "zcoder_url" {
  value       = "https://${var.zcoder_hostname}"
  description = "Public ZCoder WebApp URL after the proxied DNS record and tunnel ingress are active."
}

output "zcoder_api_url" {
  value       = "https://${var.zcoder_hostname}/api/"
  description = "Public ZCoder API URL routed to the FastAPI backend."
}
