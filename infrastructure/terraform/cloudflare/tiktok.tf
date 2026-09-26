# ==============================================================================
# TikTok Developer & TikTok Shop Integration for zttshop.zeaz.dev
# Documentation: https://developers.tiktok.com/doc/overview
# ==============================================================================

variable "enable_tiktok_developer_integration" {
  type        = bool
  default     = true
  description = "Enable TikTok Developer App domain verification and OAuth endpoints for zttshop.zeaz.dev."
}

variable "tiktok_client_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "TikTok Developer App Client Key (from https://developers.tiktok.com/apps)."
}

variable "tiktok_client_secret" {
  type        = string
  default     = ""
  sensitive   = true
  description = "TikTok Developer App Client Secret."
}

variable "tiktok_verification_code" {
  type        = string
  default     = ""
  description = "TikTok Domain Verification code / file content for developers.tiktok.com ownership check (tiktok-developers-site-verification=*)."
}

variable "zttato_tiktok_verification_code" {
  type        = string
  default     = "9WurARgpbnJkdus0r4bfvSZydNYNxKUC"
  description = "TikTok Domain Verification code for zttato.zeaz.dev (from web/tiktok-site-verification.txt)."
}

# ------------------------------------------------------------------------------
# TikTok Domain Ownership Verification (TXT Record) for zttshop
# ------------------------------------------------------------------------------
resource "cloudflare_dns_record" "tiktok_verification" {
  count   = var.enable_tiktok_developer_integration && var.tiktok_verification_code != "" ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = var.zttshop_hostname
  type    = "TXT"
  content = "tiktok-developers-site-verification=${var.tiktok_verification_code}"
  ttl     = 300
  comment = "TikTok Developer Portal domain verification for zttshop.zeaz.dev"
}

# ------------------------------------------------------------------------------
# TikTok Domain Ownership Verification (TXT Record) for zttato
# ------------------------------------------------------------------------------
resource "cloudflare_dns_record" "zttato_tiktok_verification" {
  count   = var.enable_tiktok_developer_integration && var.zttato_tiktok_verification_code != "" ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = var.zttato_hostname
  type    = "TXT"
  content = "tiktok-developers-site-verification=${var.zttato_tiktok_verification_code}"
  ttl     = 300
  comment = "TikTok Developer Portal domain verification for zttato.zeaz.dev"
}

# ------------------------------------------------------------------------------
# Outputs for TikTok Developer App Portal
# ------------------------------------------------------------------------------
output "tiktok_oauth_redirect_uri" {
  value       = "https://${var.zttshop_hostname}/api/auth/callback/tiktok"
  description = "TikTok Developer OAuth 2.0 Redirect URI to enter in TikTok App Console."
}

output "tiktok_terms_of_service_url" {
  value       = "https://${var.zttshop_hostname}/terms"
  description = "Public Terms of Service URL required by TikTok Developer Portal."
}

output "tiktok_privacy_policy_url" {
  value       = "https://${var.zttshop_hostname}/privacy"
  description = "Public Privacy Policy URL required by TikTok Developer Portal."
}

output "tiktok_webhook_url" {
  value       = "https://${var.zttshop_hostname}/api/webhooks/tiktok"
  description = "TikTok Developer & TikTok Shop Webhook Callback URL."
}
