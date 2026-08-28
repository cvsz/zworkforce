# ==============================================================================
# zWorkforce & ZSP Studio Cloudflare Stack Specification (*.zeaz.dev)
# ==============================================================================

variable "zwf_hostname" {
  type        = string
  default     = "zwf.zeaz.dev"
  description = "Public hostname for the zWorkforce Enterprise API & Orchestration Control Plane."

  validation {
    condition     = endswith(lower(var.zwf_hostname), ".${lower(var.zone_name)}")
    error_message = "zwf_hostname must be a subdomain of zone_name."
  }
}

variable "zwf_api_hostname" {
  type        = string
  default     = "zwf-api.zeaz.dev"
  description = "Public API hostname for the zWorkforce control plane."

  validation {
    condition     = endswith(lower(var.zwf_api_hostname), ".${lower(var.zone_name)}")
    error_message = "zwf_api_hostname must be a subdomain of zone_name."
  }
}

variable "zslog_hostname" {
  type        = string
  default     = "zslog.zeaz.dev"
  description = "Public hostname for the zslog fake-credit realtime log service."

  validation {
    condition     = endswith(lower(var.zslog_hostname), ".${lower(var.zone_name)}")
    error_message = "zslog_hostname must be a subdomain of zone_name."
  }
}

variable "zslog_origin" {
  type        = string
  default     = "http://127.0.0.1:9581"
  description = "Loopback origin published by the zslog fake-credit realtime log service."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zslog_origin))
    error_message = "zslog_origin must use a loopback address."
  }
}

variable "zwf_origin" {
  type        = string
  default     = "http://127.0.0.1:9570"
  description = "Loopback origin published by the zWorkforce API service."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zwf_origin))
    error_message = "zwf_origin must use a loopback address."
  }
}

variable "studio_hostname" {
  type        = string
  default     = "studio.zeaz.dev"
  description = "Public hostname for the ZSP Studio AI Content & HyperFrames Platform."

  validation {
    condition     = endswith(lower(var.studio_hostname), ".${lower(var.zone_name)}")
    error_message = "studio_hostname must be a subdomain of zone_name."
  }
}

variable "studio_origin" {
  type        = string
  default     = "http://127.0.0.1:3005"
  description = "Loopback origin published by the ZSP-AITool Studio Next.js application."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.studio_origin))
    error_message = "studio_origin must use a loopback address."
  }
}

variable "zarvis_hostname" {
  type        = string
  default     = "zarvis.zeaz.dev"
  description = "Public hostname for the Z.A.R.V.I.S. Autonomous Voice & Executive Assistant Gateway."

  validation {
    condition     = endswith(lower(var.zarvis_hostname), ".${lower(var.zone_name)}")
    error_message = "zarvis_hostname must be a subdomain of zone_name."
  }
}

variable "zarvis_origin" {
  type        = string
  default     = "http://127.0.0.1:9570"
  description = "Loopback origin published for Z.A.R.V.I.S. (zWorkforce API & Voice Gateway)."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zarvis_origin))
    error_message = "zarvis_origin must use a loopback address."
  }
}

variable "zider_hostname" {
  type        = string
  default     = "zider.zeaz.dev"
  description = "Public hostname for zider AI Sidebar, ChatPDF & Multi-Model Workspace."

  validation {
    condition     = endswith(lower(var.zider_hostname), ".${lower(var.zone_name)}")
    error_message = "zider_hostname must be a subdomain of zone_name."
  }
}

variable "zider_origin" {
  type        = string
  default     = "http://127.0.0.1:8085"
  description = "Loopback origin published by the zider BFF FastAPI / Node gateway."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zider_origin))
    error_message = "zider_origin must use a loopback address."
  }
}

# Canonical zWorkforce-family ingress. Keeping the host/origin pairs next to the
# DNS declarations prevents the local cloudflared manifest and managed tunnel
# configuration from silently diverging.
locals {
  zworkforce_ingress = [
    { hostname = var.zwf_hostname, service = var.zwf_origin },
    { hostname = var.zwf_api_hostname, service = var.zwf_origin },
    { hostname = var.zslog_hostname, service = var.zslog_origin },
    { hostname = var.studio_hostname, service = var.studio_origin },
    { hostname = var.zarvis_hostname, service = var.zarvis_origin },
    { hostname = var.zider_hostname, service = var.zider_origin },
    { hostname = var.mcp_hostname, service = var.mcp_origin },
  ]

  ha_ingress = [
    { hostname = var.ha_a_hostname, service = "http://${var.ha_a_ip}:9456" },
    { hostname = var.ha_b_hostname, service = "http://${var.ha_b_ip}:9456" },
    { hostname = var.obs_hostname, service = "http://${var.obs_ip}:9456" },
    { hostname = var.core_hostname, service = "http://${var.core_ip}:80" },
  ]
}

resource "cloudflare_dns_record" "zwf" {
  zone_id = var.cloudflare_zone_id
  name    = var.zwf_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zWorkforce Control Plane via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zwf_api" {
  zone_id = var.cloudflare_zone_id
  name    = var.zwf_api_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zWorkforce API via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zslog" {
  zone_id = var.cloudflare_zone_id
  name    = var.zslog_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zWorkforce log surface alias via Cloudflare Tunnel"
}

# Keep the former public hostname during the migration window.  Retiring this
# record is a separate, post-cutover change after zwf-api.zeaz.dev has passed
# DNS, tunnel, health, and rollback verification.
resource "cloudflare_dns_record" "zworkforce" {
  zone_id = var.cloudflare_zone_id
  name    = "zworkforce.zeaz.dev"
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zWorkforce production HTTPS endpoint via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "studio" {
  zone_id = var.cloudflare_zone_id
  name    = var.studio_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZSP-AITool Studio via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zarvis" {
  zone_id = var.cloudflare_zone_id
  name    = var.zarvis_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "Z.A.R.V.I.S. Autonomous Voice Assistant via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zider" {
  zone_id = var.cloudflare_zone_id
  name    = var.zider_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zider AI Browser Sidebar & Multi-Model Workspace via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "mcp" {
  zone_id = var.cloudflare_zone_id
  name    = var.mcp_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zWorkforce standard-MCP bridge via Cloudflare Tunnel"
}

output "zwf_url" {
  value       = "https://${var.zwf_hostname}"
  description = "Public zWorkforce Control Plane URL."
}

output "zwf_api_url" {
  value       = "https://${var.zwf_api_hostname}"
  description = "Public zWorkforce API URL."
}

output "zslog_url" {
  value       = "https://${var.zslog_hostname}"
  description = "Public zslog realtime log service URL."
}

output "studio_url" {
  value       = "https://${var.studio_hostname}"
  description = "Public ZSP-AITool Studio URL."
}

output "zarvis_url" {
  value       = "https://${var.zarvis_hostname}"
  description = "Public Z.A.R.V.I.S. Autonomous Voice Assistant URL."
}

output "zider_url" {
  value       = "https://${var.zider_hostname}"
  description = "Public zider AI Browser Sidebar & Workspace URL."
}
