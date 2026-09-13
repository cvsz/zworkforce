variable "zneon_hostname" {
  type        = string
  default     = "zneon.zeaz.dev"
  description = "Public hostname for the zNeonDrive studio and game project website."

  validation {
    condition     = endswith(lower(var.zneon_hostname), ".${lower(var.zone_name)}")
    error_message = "zneon_hostname must be a subdomain of zone_name."
  }
}

variable "zneon_origin" {
  type        = string
  default     = "http://127.0.0.1:18085"
  description = "Dedicated loopback origin published by the zNeonDrive web container for Cloudflare Tunnel."

  validation {
    condition     = var.zneon_origin == "http://127.0.0.1:18085"
    error_message = "zneon_origin must use the reviewed loopback web origin at http://127.0.0.1:18085."
  }
}

resource "cloudflare_dns_record" "zneon" {
  zone_id = var.cloudflare_zone_id
  name    = var.zneon_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zNeonDrive public website via Cloudflare Tunnel"
}

locals {
  zneon_ingress = [
    {
      hostname = var.zneon_hostname
      service  = var.zneon_origin
    },
  ]
}

output "zneon_url" {
  value       = "https://${var.zneon_hostname}"
  description = "Public zNeonDrive URL after the proxied DNS record and tunnel ingress are active."
}
