######################################################################
# MoneyPrinterTurbo WebUI
# Publishes the local Streamlit WebUI through the existing Cloudflare
# Tunnel at mpt.zeaz.dev.
######################################################################

variable "enable_mpt" {
  type        = bool
  default     = true
  description = "Create the MoneyPrinterTurbo DNS record and tunnel ingress route."
}

variable "mpt_hostname" {
  type        = string
  default     = "mpt.zeaz.dev"
  description = "Public hostname for the MoneyPrinterTurbo WebUI."

  validation {
    condition     = endswith(lower(var.mpt_hostname), ".${lower(var.zone_name)}")
    error_message = "mpt_hostname must be a subdomain of zone_name (${var.zone_name})."
  }
}

variable "mpt_origin" {
  type        = string
  default     = "http://127.0.0.1:8501"
  description = "Loopback Streamlit origin used by the MoneyPrinterTurbo WebUI."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.mpt_origin))
    error_message = "mpt_origin must use a loopback http://127.0.0.1:<port> address."
  }
}

locals {
  mpt_ingress = var.enable_mpt ? [
    { hostname = var.mpt_hostname, service = var.mpt_origin },
  ] : []
}

resource "cloudflare_dns_record" "mpt" {
  count   = var.enable_mpt ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = var.mpt_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "MoneyPrinterTurbo WebUI via Cloudflare Tunnel"
}

output "mpt_url" {
  value       = "https://${var.mpt_hostname}"
  description = "Public MoneyPrinterTurbo WebUI URL."
}
