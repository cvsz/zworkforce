variable "cloudflare_api_token" {
  type        = string
  sensitive   = true
  description = "Scoped Cloudflare API token with Zone DNS, Tunnel and Access permissions."

  validation {
    condition     = length(trimspace(var.cloudflare_api_token)) >= 20
    error_message = "cloudflare_api_token must be a real scoped token."
  }
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare account ID."

  validation {
    condition     = can(regex("^[0-9a-f]{32}$", lower(var.cloudflare_account_id)))
    error_message = "cloudflare_account_id must be a 32-character hexadecimal ID."
  }
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Cloudflare zone ID for the managed domain."

  validation {
    condition     = can(regex("^[0-9a-f]{32}$", lower(var.cloudflare_zone_id)))
    error_message = "cloudflare_zone_id must be a 32-character hexadecimal ID."
  }
}

variable "cloudflare_tunnel_id" {
  type        = string
  description = "Existing Cloudflare Tunnel UUID used by z-platform."

  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.cloudflare_tunnel_id))
    error_message = "cloudflare_tunnel_id must be a valid UUID."
  }
}

variable "manage_tunnel_config" {
  type        = bool
  description = "When true, Terraform owns the existing tunnel ingress configuration. Keep false until the current remote configuration has been imported and reviewed."
  default     = false
}

variable "zone_name" {
  type        = string
  description = "Managed DNS zone, for example zeaz.dev."
}

variable "app_routes" {
  description = "Public hostnames routed through the existing Cloudflare Tunnel."
  type = map(object({
    hostname              = string
    service               = string
    access_enabled        = optional(bool, false)
    access_aud            = optional(string)
    allowed_emails        = optional(list(string), [])
    allowed_email_domains = optional(list(string), [])
  }))

  validation {
    condition = alltrue([
      for route in values(var.app_routes) :
      endswith(lower(route.hostname), ".${lower(var.zone_name)}") &&
      can(regex("^https?://[^[:space:]]+$", route.service))
    ])
    error_message = "Every route hostname must belong to zone_name and service must be an HTTP(S) URL reachable by cloudflared."
  }
}

variable "manage_free_access" {
  type        = bool
  description = "Manage Cloudflare Access applications for protected routes. Keep false until existing Access applications are imported."
  nullable    = false
  default     = false
}

variable "free_access_session_duration" {
  type        = string
  description = "Cloudflare Access session duration for protected routes."
  nullable    = false
  default     = "8h"

  validation {
    condition     = can(regex("^[0-9]+(m|h|d)$", var.free_access_session_duration))
    error_message = "free_access_session_duration must use minutes, hours, or days (for example 8h)."
  }
}

variable "free_access_require_mfa" {
  type        = bool
  description = "Require MFA for Free-mode Access policies."
  nullable    = false
  default     = true
}

variable "free_access_allowed_idps" {
  type        = list(string)
  description = "Existing Cloudflare Access identity provider IDs allowed for Free-mode applications."
  nullable    = false
  default     = []
}

variable "free_access_service_token_ids" {
  type        = list(string)
  description = "Cloudflare Access service token IDs allowed to probe protected Free-mode applications."
  nullable    = false
  default     = []
}
