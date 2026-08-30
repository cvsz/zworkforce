# Legacy hostnames retained for state compatibility.
# These were part of the pre-consolidation Moopiew stack (moopiew.zeaz.dev, etc.)
# and remain in remote state. Declare them to keep `terraform validate` and
# `terraform plan` from failing on stray tfvars entries. New deployments should
# prefer the consolidated per-service files (zworkforce.tf, zksato.tf, etc.)
# and the `app_routes` contract.

variable "moopiew_hostname" {
  type        = string
  default     = "moopiew.zeaz.dev"
  description = "Legacy Moopiew hostname (pre-consolidation)."
  validation {
    condition     = endswith(lower(var.moopiew_hostname), ".${lower(var.zone_name)}")
    error_message = "moopiew_hostname must be a subdomain of zone_name."
  }
}
variable "moopiew_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Legacy Moopiew origin."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.moopiew_origin))
    error_message = "moopiew_origin must use loopback."
  }
}
variable "arin_hostname" {
  type        = string
  default     = "arin.zeaz.dev"
  description = "Legacy Arin hostname."
  validation {
    condition     = endswith(lower(var.arin_hostname), ".${lower(var.zone_name)}")
    error_message = "arin_hostname must be a subdomain of zone_name."
  }
}
variable "arin_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Legacy Arin origin."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.arin_origin))
    error_message = "arin_origin must use loopback."
  }
}
variable "zttshop_hostname" {
  type        = string
  default     = "zttshop.zeaz.dev"
  description = "Legacy zttshop hostname."
  validation {
    condition     = endswith(lower(var.zttshop_hostname), ".${lower(var.zone_name)}")
    error_message = "zttshop_hostname must be a subdomain of zone_name."
  }
}
variable "zttshop_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Legacy zttshop origin."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zttshop_origin))
    error_message = "zttshop_origin must use loopback."
  }
}
variable "chat_hostname" {
  type        = string
  default     = "chat.zeaz.dev"
  description = "Legacy chat hostname."
  validation {
    condition     = endswith(lower(var.chat_hostname), ".${lower(var.zone_name)}")
    error_message = "chat_hostname must be a subdomain of zone_name."
  }
}
variable "chat_origin" {
  type        = string
  default     = "http://127.0.0.1:3080"
  description = "Legacy chat origin."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.chat_origin))
    error_message = "chat_origin must use loopback."
  }
}
variable "piewdash_hostname" {
  type        = string
  default     = "piewdash.zeaz.dev"
  description = "Legacy piewdash hostname."
  validation {
    condition     = endswith(lower(var.piewdash_hostname), ".${lower(var.zone_name)}")
    error_message = "piewdash_hostname must be a subdomain of zone_name."
  }
}
variable "piewdash_origin" {
  type        = string
  default     = "http://127.0.0.1:80"
  description = "Legacy piewdash origin."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.piewdash_origin))
    error_message = "piewdash_origin must use loopback."
  }
}
variable "piewdash_access_allowed_emails" {
  type        = set(string)
  default     = []
  description = "Legacy piewdash Access allow list."
  validation {
    condition = alltrue([
      for email in var.piewdash_access_allowed_emails :
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", lower(email)))
    ])
    error_message = "piewdash_access_allowed_emails must be valid emails."
  }
}
variable "zerp_hostname" {
  type        = string
  default     = "zerp.zeaz.dev"
  description = "Legacy zerp hostname."
  validation {
    condition     = endswith(lower(var.zerp_hostname), ".${lower(var.zone_name)}")
    error_message = "zerp_hostname must be a subdomain of zone_name."
  }
}
variable "zerp_origin" {
  type        = string
  default     = "http://127.0.0.1:80"
  description = "Legacy zerp origin."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zerp_origin))
    error_message = "zerp_origin must use loopback."
  }
}
variable "mcp_hostname" {
  type        = string
  default     = "mcp.zeaz.dev"
  description = "mcp hostname (moved to zworkforce.tf but kept for tfvars compatibility)."
  validation {
    condition     = endswith(lower(var.mcp_hostname), ".${lower(var.zone_name)}")
    error_message = "mcp_hostname must be a subdomain of zone_name."
  }
}
variable "mcp_origin" {
  type        = string
  default     = "http://127.0.0.1:9580"
  description = "mcp origin."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.mcp_origin))
    error_message = "mcp_origin must use loopback."
  }
}
variable "core_hostname" {
  type        = string
  default     = "core.zeaz.dev"
  description = "Legacy core hostname."
  validation {
    condition     = endswith(lower(var.core_hostname), ".${lower(var.zone_name)}")
    error_message = "core_hostname must be a subdomain of zone_name."
  }
}
variable "core_ip" {
  type        = string
  default     = "192.168.182.234"
  description = "Legacy core IP."
}
variable "ha_a_hostname" {
  type        = string
  default     = "ha-a.zeaz.dev"
  description = "Legacy ha-a hostname."
  validation {
    condition     = endswith(lower(var.ha_a_hostname), ".${lower(var.zone_name)}")
    error_message = "ha_a_hostname must be a subdomain of zone_name."
  }
}
variable "ha_a_ip" {
  type        = string
  default     = "192.168.74.134"
  description = "Legacy ha-a IP."
}
variable "ha_b_hostname" {
  type        = string
  default     = "ha-b.zeaz.dev"
  description = "Legacy ha-b hostname."
  validation {
    condition     = endswith(lower(var.ha_b_hostname), ".${lower(var.zone_name)}")
    error_message = "ha_b_hostname must be a subdomain of zone_name."
  }
}
variable "ha_b_ip" {
  type        = string
  default     = "192.168.74.135"
  description = "Legacy ha-b IP."
}
variable "obs_hostname" {
  type        = string
  default     = "obs.zeaz.dev"
  description = "Legacy obs hostname."
  validation {
    condition     = endswith(lower(var.obs_hostname), ".${lower(var.zone_name)}")
    error_message = "obs_hostname must be a subdomain of zone_name."
  }
}
variable "obs_ip" {
  type        = string
  default     = "192.168.74.130"
  description = "Legacy obs IP."
}
