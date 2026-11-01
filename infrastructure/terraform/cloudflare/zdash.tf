variable "zdash_hostname" {
  type        = string
  default     = "zdash.zeaz.dev"
  description = "Protected hostname for the zDash operations dashboard."

  validation {
    condition     = endswith(lower(var.zdash_hostname), ".${lower(var.zone_name)}")
    error_message = "zdash_hostname must be a subdomain of zone_name."
  }
}

variable "zdash_origin" {
  type        = string
  default     = "http://127.0.0.1:18080"
  description = "Loopback-only zDash gateway reached by cloudflared."

  validation {
    condition     = var.zdash_origin == "http://127.0.0.1:18080"
    error_message = "zdash_origin must use the reviewed local gateway at http://127.0.0.1:18080."
  }
}

variable "zdash_access_allowed_emails" {
  type        = set(string)
  default     = []
  description = "Exact operator emails allowed through Cloudflare Access. Empty inherits piewdash_access_allowed_emails."

  validation {
    condition = alltrue([
      for email in var.zdash_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", lower(email)))
    ])
    error_message = "zdash_access_allowed_emails must contain only valid operator emails."
  }
}

locals {
  zdash_access_allowed_emails = length(var.zdash_access_allowed_emails) > 0 ? var.zdash_access_allowed_emails : var.piewdash_access_allowed_emails
}

resource "cloudflare_dns_record" "zdash" {
  zone_id = var.cloudflare_zone_id
  name    = var.zdash_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "Protected zDash operations dashboard via Cloudflare Tunnel"
}

output "zdash_url" {
  value       = "https://${var.zdash_hostname}"
  description = "Protected zDash URL after DNS and tunnel ingress are active."
}
