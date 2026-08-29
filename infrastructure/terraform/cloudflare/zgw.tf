variable "zgw_hostname" {
  type        = string
  default     = "zgw.zeaz.dev"
  description = "SSH gateway hostname for ha-node-a access."

  validation {
    condition     = endswith(lower(var.zgw_hostname), ".${lower(var.zone_name)}")
    error_message = "zgw_hostname must be a subdomain of zone_name."
  }
}

variable "zgw_ssh_target" {
  type        = string
  default     = "ssh://cvsz@192.168.74.134:22"
  description = "SSH target service for the zgw gateway."
}

resource "cloudflare_dns_record" "zgw" {
  zone_id = var.cloudflare_zone_id
  name    = var.zgw_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "SSH gateway for ha-node-a via Cloudflare Tunnel"
}

output "zgw_ssh_command" {
  value       = "cloudflared access ssh --hostname ${var.zgw_hostname}"
  description = "SSH command to connect through the zgw gateway."
}
