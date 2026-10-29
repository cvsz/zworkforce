variable "cme_access_service_token_id" {
  type        = string
  description = "Cloudflare Access service-token ID used by machine verification. Supply from protected operator configuration; never commit its secret."
  validation {
    condition     = length(trimspace(var.cme_access_service_token_id)) > 0
    error_message = "cme_access_service_token_id must identify the provisioned verification service token."
  }
}

# CMe ownership contract.
# DNS and origin are already managed by cloudflare_dns_record.cmeerp and
# var.cmeerp_* in main.tf/variables.tf. Do not create a second state address.

resource "cloudflare_zero_trust_access_application" "cme" {
  account_id                 = var.cloudflare_account_id
  name                       = "CMe Production Application"
  domain                     = var.cmeerp_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [
    {
      name       = "Approved CMe operators"
      precedence = 1
      decision   = "allow"
      include = [
        for email in sort(tolist(var.cme_access_allowed_emails)) :
        { email = { email = lower(email) } }
      ]
    },
    {
      name       = "CMe machine verification"
      precedence = 2
      decision   = "non_identity"
      include = [{
        service_token = { token_id = var.cme_access_service_token_id }
      }]
    }
  ]
}

output "cme_url" {
  value       = "https://${var.cmeerp_hostname}"
  description = "Protected CMe URL after DNS, tunnel ingress, and Cloudflare Access are active."
}
