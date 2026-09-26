# ==============================================================================
# LLM Wiki web client (*.zeaz.dev)
# ==============================================================================
# Ported from the unmanaged copy in the `zeaz` repository, which had never been
# applied: the hostname had no DNS record and no tunnel ingress, so
# llmwiki.zeaz.dev returned 404.
#
# Published on the shared tunnel with the reviewed Vite preview origin. The
# origin is the built client's primary loopback port; a second preview port may
# exist locally, so keep this value in step with the running preview.

variable "llmwiki_hostname" {
  type        = string
  default     = "llmwiki.zeaz.dev"
  description = "Public hostname for the LLM Wiki web client."

  validation {
    condition     = endswith(lower(var.llmwiki_hostname), ".${lower(var.zone_name)}")
    error_message = "llmwiki_hostname must be a subdomain of zone_name."
  }
}

variable "llmwiki_origin" {
  type        = string
  default     = "http://127.0.0.1:5173"
  description = "Primary loopback Vite preview origin for the built LLM Wiki web client."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:5173$", var.llmwiki_origin))
    error_message = "llmwiki_origin must use the reviewed LLM Wiki preview origin at http://127.0.0.1:5173."
  }
}

resource "cloudflare_dns_record" "llmwiki" {
  zone_id = var.cloudflare_zone_id
  name    = var.llmwiki_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "LLM Wiki web client via Cloudflare Tunnel"
}

output "llmwiki_url" {
  value       = "https://${var.llmwiki_hostname}"
  description = "Public LLM Wiki URL after the proxied DNS record and tunnel ingress are active."
}
