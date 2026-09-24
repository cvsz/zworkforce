variable "cloudflare_api_token" {
  type        = string
  sensitive   = true
  description = "Scoped Cloudflare API token. Supply through TF_VAR_cloudflare_api_token only."

  validation {
    condition     = length(trimspace(var.cloudflare_api_token)) >= 20
    error_message = "cloudflare_api_token must be a real scoped token."
  }
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare account ID owning the existing tunnel."
  validation {
    condition     = can(regex("^[0-9a-f]{32}$", lower(var.cloudflare_account_id)))
    error_message = "cloudflare_account_id must be 32 hexadecimal characters."
  }
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Cloudflare zone ID for zeaz.dev."
  validation {
    condition     = can(regex("^[0-9a-f]{32}$", lower(var.cloudflare_zone_id)))
    error_message = "cloudflare_zone_id must be 32 hexadecimal characters."
  }
}

variable "cloudflare_tunnel_id" {
  type        = string
  description = "Existing Cloudflare Tunnel ID, as a UUID or a 32-character hexadecimal value."
  validation {
    condition     = can(regex("^[0-9a-fA-F]{32}$", var.cloudflare_tunnel_id)) || can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.cloudflare_tunnel_id))
    error_message = "cloudflare_tunnel_id must be a UUID or 32 hexadecimal characters."
  }
}

variable "zone_name" {
  type        = string
  default     = "zeaz.dev"
  description = "The DNS zone containing the application hostname."
}

variable "moopiew_hostname" {
  type        = string
  default     = "moopiew.zeaz.dev"
  description = "Public hostname for the Moopiew preorder app."
  validation {
    condition     = endswith(lower(var.moopiew_hostname), ".${lower(var.zone_name)}")
    error_message = "moopiew_hostname must be a subdomain of zone_name."
  }
}

variable "moopiew_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Loopback Caddy origin reached by cloudflared for the public application."
  validation {
    condition     = var.moopiew_origin == "http://127.0.0.1:8080"
    error_message = "moopiew_origin must use the reviewed loopback Caddy proxy at http://127.0.0.1:8080."
  }
}

variable "arin_hostname" {
  type        = string
  default     = "arin.zeaz.dev"
  description = "Public hostname for the Arin static marketing site."
  validation {
    condition     = endswith(lower(var.arin_hostname), ".${lower(var.zone_name)}")
    error_message = "arin_hostname must be a subdomain of zone_name."
  }
}

variable "arin_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Loopback Caddy origin serving the Arin static site."
  validation {
    condition     = var.arin_origin == "http://127.0.0.1:8080"
    error_message = "arin_origin must use the reviewed loopback Caddy proxy at http://127.0.0.1:8080."
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

variable "zttshop_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Loopback Caddy origin reached by cloudflared for zttshop."
  validation {
    condition     = var.zttshop_origin == "http://127.0.0.1:8080"
    error_message = "zttshop_origin must use the reviewed loopback Caddy proxy at http://127.0.0.1:8080."
  }
}

variable "qwen_hostname" {
  type        = string
  default     = "qwen.zeaz.dev"
  description = "Public hostname for the Qwen chat interface."
  validation {
    condition     = endswith(lower(var.qwen_hostname), ".${lower(var.zone_name)}")
    error_message = "qwen_hostname must be a subdomain of zone_name."
  }
}

variable "qwen_origin" {
  type        = string
  default     = "http://127.0.0.1:8091"
  description = "Loopback origin reached by cloudflared for the Qwen chat interface."
  validation {
    condition     = var.qwen_origin == "http://127.0.0.1:8091"
    error_message = "qwen_origin must use the reviewed loopback origin at http://127.0.0.1:8091."
  }
}

variable "chat_hostname" {
  type        = string
  default     = "chat.zeaz.dev"
  description = "Public hostname for the OpenWebUI chat interface."
  validation {
    condition     = endswith(lower(var.chat_hostname), ".${lower(var.zone_name)}")
    error_message = "chat_hostname must be a subdomain of zone_name."
  }
}

variable "chat_origin" {
  type        = string
  default     = "http://127.0.0.1:3000"
  description = "Host-loopback origin published by the OpenWebUI container."
  validation {
    condition     = var.chat_origin == "http://127.0.0.1:3000" || var.chat_origin == "http://127.0.0.1:3080"
    error_message = "chat_origin must use the reviewed OpenWebUI host port at http://127.0.0.1:3000 or the deployed host port at http://127.0.0.1:3080."
  }
}

variable "piewdash_hostname" {
  type        = string
  default     = "piewdash.zeaz.dev"
  description = "Public hostname for the MooPiew engineering dashboard."
  validation {
    condition     = endswith(lower(var.piewdash_hostname), ".${lower(var.zone_name)}")
    error_message = "piewdash_hostname must be a subdomain of zone_name."
  }
}

variable "piewdash_origin" {
  type        = string
  default     = "http://127.0.0.1:80"
  description = "Loopback Caddy origin reached by cloudflared for the protected dashboard."
  validation {
    condition     = var.piewdash_origin == "http://127.0.0.1:80"
    error_message = "piewdash_origin must use the reviewed Caddy authentication proxy at http://127.0.0.1:80."
  }
}

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

variable "zerp_hostname" {
  type        = string
  default     = "zerp.zeaz.dev"
  description = "Public hostname for the zERP web application."
  validation {
    condition     = endswith(lower(var.zerp_hostname), ".${lower(var.zone_name)}")
    error_message = "zerp_hostname must be a subdomain of zone_name."
  }
}

variable "zerp_origin" {
  type        = string
  default     = "http://127.0.0.1:80"
  description = "Loopback Caddy origin reached by cloudflared for zERP."
  validation {
    condition     = var.zerp_origin == "http://127.0.0.1:80"
    error_message = "zerp_origin must use the reviewed loopback Caddy proxy at http://127.0.0.1:80."
  }
}

variable "manage_tunnel_config" {
  type        = bool
  default     = false
  description = "Only true after importing and reviewing the current remote tunnel ingress."
}

variable "cmeerp_hostname" {
  type        = string
  default     = "cme.zeaz.dev"
  description = "Public hostname for the CME Pro ERP web application."
  validation {
    condition     = endswith(lower(var.cmeerp_hostname), ".${lower(var.zone_name)}")
    error_message = "cmeerp_hostname must be a subdomain of zone_name."
  }
}

variable "cmeerp_origin" {
  type        = string
  default     = "http://127.0.0.1:8001"
  description = "Loopback origin reached by cloudflared for CME Pro ERP."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.cmeerp_origin))
    error_message = "cmeerp_origin must use a loopback address."
  }
}

variable "zai_hostname" {
  type        = string
  default     = "zai.zeaz.dev"
  description = "Public hostname for the ZEAZ AI Command Center."
  validation {
    condition     = endswith(lower(var.zai_hostname), ".${lower(var.zone_name)}")
    error_message = "zai_hostname must be a subdomain of zone_name."
  }
}

variable "zai_origin" {
  type        = string
  default     = "http://127.0.0.1:8765"
  description = "Loopback origin reached by cloudflared for ZEAZ AI Command Center."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zai_origin))
    error_message = "zai_origin must use a loopback address."
  }
}

variable "auth_hostname" {
  type        = string
  default     = "auth.zeaz.dev"
  description = "Public hostname for the ZEAZ Authentication Portal."
  validation {
    condition     = endswith(lower(var.auth_hostname), ".${lower(var.zone_name)}")
    error_message = "auth_hostname must be a subdomain of zone_name."
  }
}

variable "auth_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Loopback origin reached by cloudflared for ZEAZ Authentication Portal."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.auth_origin))
    error_message = "auth_origin must use a loopback address."
  }
}

variable "laps_hostname" {
  type        = string
  default     = "laps.zeaz.dev"
  description = "Public hostname for the ZEAZ LAPS (Local Administrator Password Solution) service."
  validation {
    condition     = endswith(lower(var.laps_hostname), ".${lower(var.zone_name)}")
    error_message = "laps_hostname must be a subdomain of zone_name."
  }
}

variable "laps_origin" {
  type        = string
  default     = "http://127.0.0.1:8080"
  description = "Loopback origin reached by cloudflared for the LAPS service."
  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.laps_origin))
    error_message = "laps_origin must use a loopback address."
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
  description = "Private IP for the observability host (defaults to HA node A until a dedicated obs host is provisioned)."
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
  description = "Public hostname for the zWorkforce standard-MCP bridge used by Anthropic MCP connectors."

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

variable "zmovie_hostname" {
  type        = string
  default     = "zmovie.zeaz.dev"
  description = "Public hostname for the zMovie AI production studio."

  validation {
    condition     = endswith(lower(var.zmovie_hostname), ".${lower(var.zone_name)}")
    error_message = "zmovie_hostname must be a subdomain of zone_name."
  }
}

variable "zmovie_origin" {
  type        = string
  default     = "http://127.0.0.1:80"
  description = "Loopback origin for zMovie WordPress at Nginx port 80."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.zmovie_origin))
    error_message = "zmovie_origin must use a loopback address."
  }
}

variable "license_hostname" {
  type        = string
  default     = "license.zeaz.dev"
  description = "Public hostname for the first-party ZeaZ License Server (Nginx ingress)."

  validation {
    condition     = endswith(lower(var.license_hostname), ".${lower(var.zone_name)}")
    error_message = "license_hostname must be a subdomain of zone_name."
  }
}

variable "license_origin" {
  type        = string
  default     = "http://127.0.0.1:80"
  description = "Loopback origin for the License Server at Nginx port 80 (Host-routed)."

  validation {
    condition     = can(regex("^http://127\\.0\\.0\\.1:[0-9]+$", var.license_origin))
    error_message = "license_origin must use a loopback address."
  }
}
