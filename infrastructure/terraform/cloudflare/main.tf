locals {
  tunnel_id_compact = lower(replace(var.cloudflare_tunnel_id, "-", ""))
  tunnel_uuid = format(
    "%s-%s-%s-%s-%s",
    substr(local.tunnel_id_compact, 0, 8),
    substr(local.tunnel_id_compact, 8, 4),
    substr(local.tunnel_id_compact, 12, 4),
    substr(local.tunnel_id_compact, 16, 4),
    substr(local.tunnel_id_compact, 20, 12),
  )
  tunnel_cname = "${local.tunnel_uuid}.cfargotunnel.com"
}

resource "cloudflare_dns_record" "moopiew" {
  zone_id = var.cloudflare_zone_id
  name    = var.moopiew_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "Moopiew preorder via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "arin" {
  zone_id = var.cloudflare_zone_id
  name    = var.arin_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "Arin static site via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zttshop" {
  zone_id = var.cloudflare_zone_id
  name    = var.zttshop_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "zttshop public app via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "qwen" {
  zone_id = var.cloudflare_zone_id
  name    = var.qwen_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "Qwen chat interface via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "chat" {
  zone_id = var.cloudflare_zone_id
  name    = var.chat_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "OpenWebUI chat via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "piewdash" {
  zone_id = var.cloudflare_zone_id
  name    = var.piewdash_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "MooPiew engineering dashboard via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zerp" {
  zone_id = var.cloudflare_zone_id
  name    = var.zerp_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZEAZ ERP via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "cmeerp" {
  zone_id = var.cloudflare_zone_id
  name    = var.cmeerp_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "CME Pro ERP via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "zai" {
  zone_id = var.cloudflare_zone_id
  name    = var.zai_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZEAZ AI Command Center via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "auth" {
  zone_id = var.cloudflare_zone_id
  name    = var.auth_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZEAZ Authentication Portal via Cloudflare Tunnel"
}

resource "cloudflare_zero_trust_access_application" "piewdash" {
  account_id                 = var.cloudflare_account_id
  name                       = "MooPiew Engineering Dashboard"
  domain                     = var.piewdash_hostname
  type                       = "self_hosted"
  session_duration           = "8h"
  app_launcher_visible       = false
  enable_binding_cookie      = true
  http_only_cookie_attribute = true

  policies = [{
    name       = "Approved dashboard operators"
    precedence = 1
    decision   = "allow"
    include = [
      for email in sort(tolist(var.piewdash_access_allowed_emails)) :
      { email = { email = lower(email) } }
    ]
  }]
}

resource "cloudflare_dns_record" "laps" {
  zone_id = var.cloudflare_zone_id
  name    = var.laps_hostname
  type    = "CNAME"
  content = local.tunnel_cname
  ttl     = 1
  proxied = true
  comment = "ZEAZ LAPS service via Cloudflare Tunnel"
}

resource "cloudflare_dns_record" "ha_a" {
  zone_id = var.cloudflare_zone_id
  name    = var.ha_a_hostname
  type    = "A"
  content = var.ha_a_ip
  ttl     = 1
  proxied = false
  comment = "HA node A private IP"
}

resource "cloudflare_dns_record" "ha_b" {
  zone_id = var.cloudflare_zone_id
  name    = var.ha_b_hostname
  type    = "A"
  content = var.ha_b_ip
  ttl     = 1
  proxied = false
  comment = "HA node B private IP"
}

resource "cloudflare_dns_record" "obs" {
  zone_id = var.cloudflare_zone_id
  name    = var.obs_hostname
  type    = "A"
  content = var.obs_ip
  ttl     = 1
  proxied = false
  comment = "Observability host private IP"
}

resource "cloudflare_dns_record" "core" {
  zone_id = var.cloudflare_zone_id
  name    = var.core_hostname
  type    = "A"
  content = var.core_ip
  ttl     = 1
  proxied = false
  comment = "Windows build host private IP"
}

# This is deliberately opt-in: applying it without first importing a live
# tunnel configuration could replace unrelated ingress rules.
resource "cloudflare_zero_trust_tunnel_cloudflared_config" "moopiew" {
  count      = var.manage_tunnel_config ? 1 : 0
  account_id = var.cloudflare_account_id
  tunnel_id  = local.tunnel_uuid
  source     = "cloudflare"

  config = {
    ingress = concat(
      [
        { hostname = var.moopiew_hostname, service = var.moopiew_origin },
        { hostname = var.zttshop_hostname, service = var.zttshop_origin },
        { hostname = var.qwen_hostname, service = var.qwen_origin },
        { hostname = var.chat_hostname, service = var.chat_origin },
        { hostname = var.piewdash_hostname, service = var.piewdash_origin },
        { hostname = var.zdash_hostname, service = var.zdash_origin },
        { hostname = var.zerp_hostname, service = var.zerp_origin },
        { hostname = var.cmeerp_hostname, service = var.cmeerp_origin },
        { hostname = var.arin_hostname, service = var.arin_origin },
        { hostname = var.zai_hostname, service = var.zai_origin },
        { hostname = var.autoc_hostname, service = var.autoc_origin },
        { hostname = var.zany_hostname, service = var.zany_origin },
        { hostname = var.zslog_hostname, service = var.zslog_origin },
        { hostname = var.auth_hostname, service = var.auth_origin },
        { hostname = var.laps_hostname, service = var.laps_origin },
      ],
      local.zworkforce_ingress,
      local.zeaz_one_ingress,
      [{ service = "http_status:404" }],
    )
  }
}
