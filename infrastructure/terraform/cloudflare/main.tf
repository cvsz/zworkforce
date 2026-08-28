locals {
  tunnel_cname = "${var.cloudflare_tunnel_id}.cfargotunnel.com"

  ingress = [
    for key in sort(keys(var.app_routes)) : {
      hostname = var.app_routes[key].hostname
      service  = var.app_routes[key].service
    }
  ]
}

resource "cloudflare_dns_record" "app_routes" {
  for_each = var.app_routes

  zone_id = var.cloudflare_zone_id
  name    = each.value.hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "z-platform ${each.key} via Cloudflare Tunnel"
}

resource "terraform_data" "route_contract" {
  for_each = var.app_routes

  input = {
    hostname       = each.value.hostname
    service        = each.value.service
    access_enabled = each.value.access_enabled
  }

  lifecycle {
    precondition {
      condition     = each.value.access_enabled == false || length(each.value.allowed_emails) + length(each.value.allowed_email_domains) > 0
      error_message = "Access-enabled routes must define allowed_emails or allowed_email_domains."
    }
  }
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "platform" {
  count      = var.manage_tunnel_config ? 1 : 0
  account_id = var.cloudflare_account_id
  tunnel_id  = var.cloudflare_tunnel_id
  source     = "cloudflare"

  config = {
    ingress = concat(
      [
        for key in sort(keys(var.app_routes)) : {
          hostname = var.app_routes[key].hostname
          service  = var.app_routes[key].service
        }
      ],
      [{ service = "http_status:404" }]
    )
  }
}
