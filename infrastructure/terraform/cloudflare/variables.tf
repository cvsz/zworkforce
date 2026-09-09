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

# Compatibility variables still referenced by legacy Cloudflare resources that
# coexist with the consolidated app_routes model. These preserve the reviewed
# defaults and fail-closed ownership behavior until those resources migrate.
variable "piewdash_access_allowed_emails" {
  type        = set(string)
  description = "Exact operator emails allowed through Cloudflare Access."

  validation {
    condition = length(var.piewdash_access_allowed_emails) > 0 && alltrue([
      for email in var.piewdash_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", lower(email)))
    ])
    error_message = "piewdash_access_allowed_emails must contain at least one valid operator email."
  }
}

variable "zttshop_hostname" {
  type        = string
  default     = "zttshop.zeaz.dev"
  description = "Public hostname for the zttshop web application."
  validation {
    condition     = endswith(lower(var.zttshop_hostname), ".${lower(var.zone_name)}")
    error_message = "zttshop_hostname must be a subdomain of zone_name."
  }
}

variable "ha_a_hostname" {
  type        = string
  default     = "ha-a.zeaz.dev"
  description = "Private hostname for HA node A."
  validation {
    condition     = endswith(lower(var.ha_a_hostname), ".${lower(var.zone_name)}")
    error_message = "ha_a_hostname must be a subdomain of zone_name."
  }
}

variable "ha_a_ip" {
  type        = string
  default     = "192.168.74.134"
  description = "Private IP for HA node A."
}

variable "ha_b_hostname" {
  type        = string
  default     = "ha-b.zeaz.dev"
  description = "Private hostname for HA node B."
  validation {
    condition     = endswith(lower(var.ha_b_hostname), ".${lower(var.zone_name)}")
    error_message = "ha_b_hostname must be a subdomain of zone_name."
  }
}

variable "ha_b_ip" {
  type        = string
  default     = "192.168.74.135"
  description = "Private IP for HA node B."
}

variable "obs_hostname" {
  type        = string
  default     = "obs.zeaz.dev"
  description = "Private hostname for the observability host."
  validation {
    condition     = endswith(lower(var.obs_hostname), ".${lower(var.zone_name)}")
    error_message = "obs_hostname must be a subdomain of zone_name."
  }
}

variable "obs_ip" {
  type        = string
  default     = "192.168.74.134"
  description = "Private IP for the observability host."
}

variable "core_hostname" {
  type        = string
  default     = "core.zeaz.dev"
  description = "Private hostname for the Windows build host."
  validation {
    condition     = endswith(lower(var.core_hostname), ".${lower(var.zone_name)}")
    error_message = "core_hostname must be a subdomain of zone_name."
  }
}

variable "core_ip" {
  type        = string
  default     = "192.168.182.234"
  description = "Private IP for the Windows build host."
}

variable "mcp_hostname" {
  type        = string
  default     = "mcp.zeaz.dev"
  description = "Public hostname for the zWorkforce standard-MCP bridge."

  validation {
    condition     = endswith(lower(var.mcp_hostname), ".${lower(var.zone_name)}")
    error_message = "mcp_hostname must be a subdomain of zone_name."
  }
}

variable "mcp_origin" {
  type        = string
  default     = "http://127.0.0.1:9580"
  description = "Loopback origin published by the zWorkforce MCP HTTP bridge."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.mcp_origin))
    error_message = "mcp_origin must use a loopback address."
  }
}
