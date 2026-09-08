variable "enable_repo_fallback" {
  type        = bool
  default     = false
  description = "Enable repo-aware Under Construction Worker routes for explicitly offline ZeaZDev hostnames."
}

variable "enable_repo_fallback_wildcard_dns" {
  type        = bool
  default     = false
  description = "Create a proxied *.zeaz.dev wildcard CNAME to the existing Cloudflare Tunnel so repo hostnames without exact DNS can reach the fallback Worker. Exact DNS records continue to win over the wildcard."
}

variable "repo_fallback_sites" {
  type        = map(string)
  default     = {}
  description = "Map of offline hostname => cvsz repository name. Only these exact hostnames receive the Under Construction Worker route."

  validation {
    condition = alltrue([
      for hostname, repo in var.repo_fallback_sites :
      hostname != var.zone_name &&
      endswith(lower(hostname), ".${lower(var.zone_name)}") &&
      length(trimspace(repo)) > 0
    ])
    error_message = "repo_fallback_sites keys must be subdomains of zone_name and values must be non-empty repository names."
  }
}

resource "cloudflare_dns_record" "repo_fallback_wildcard" {
  count   = var.enable_repo_fallback && var.enable_repo_fallback_wildcard_dns ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = "*.${var.zone_name}"
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZeaZDev repo fallback; exact DNS records override this wildcard"
}

resource "cloudflare_workers_script" "repo_under_construction" {
  count              = var.enable_repo_fallback ? 1 : 0
  account_id         = var.cloudflare_account_id
  script_name        = "zeaz-repo-under-construction"
  compatibility_date = "2026-09-09"
  main_module        = "repo-under-construction.js"
  content_file       = "${path.module}/workers/repo-under-construction.js"
  content_sha256     = filesha256("${path.module}/workers/repo-under-construction.js")
}

resource "cloudflare_workers_route" "repo_under_construction" {
  for_each = var.enable_repo_fallback ? var.repo_fallback_sites : {}
  zone_id  = var.cloudflare_zone_id
  pattern  = "${each.key}/*"
  script   = cloudflare_workers_script.repo_under_construction[0].script_name
}

output "repo_under_construction_sites" {
  value       = var.enable_repo_fallback ? var.repo_fallback_sites : {}
  description = "Exact ZeaZDev hostnames currently intercepted by the repo-aware Under Construction Worker."
}
