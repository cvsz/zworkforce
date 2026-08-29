locals {
  protected_free_access_routes = {
    for key, route in var.app_routes : key => route
    if var.manage_free_access && route.access_enabled
  }
}

resource "cloudflare_zero_trust_access_application" "free_mode" {
  for_each = local.protected_free_access_routes

  account_id                = var.cloudflare_account_id
  name                      = "z-platform ${each.key}"
  domain                    = each.value.hostname
  type                      = "self_hosted"
  session_duration          = var.free_access_session_duration
  allowed_idps              = var.free_access_allowed_idps
  auto_redirect_to_identity = length(var.free_access_allowed_idps) == 1
  enable_binding_cookie     = true
  app_launcher_visible      = false
  policies = concat(
    [{
      name       = "z-platform ${each.key} allow"
      decision   = "allow"
      precedence = 1
      include = concat(
        [for domain in each.value.allowed_email_domains : {
          email_domain = { domain = domain }
        }],
        [for email in each.value.allowed_emails : {
          email = { email = email }
        }]
      )
      mfa_config = {
        mfa_disabled     = !var.free_access_require_mfa
        session_duration = var.free_access_session_duration
      }
    }],
    [for index, token_id in var.free_access_service_token_ids : {
      name       = index == 0 ? "z-platform ${each.key} service auth" : "z-platform ${each.key} service auth ${index + 1}"
      decision   = "non_identity"
      precedence = 10 + index
      include = [{
        service_token = { token_id = token_id }
      }]
    }]
  )
}
