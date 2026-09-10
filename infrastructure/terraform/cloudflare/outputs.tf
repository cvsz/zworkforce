output "dns_records" {
  description = "Cloudflare DNS records managed by this stack."
  value = merge(
    {
      for key, record in cloudflare_dns_record.app_routes : key => {
        hostname = record.name
        content  = record.content
        proxied  = record.proxied
      }
    },
    {
      zksato = {
        hostname = cloudflare_dns_record.zksato.name
        content  = cloudflare_dns_record.zksato.content
        proxied  = cloudflare_dns_record.zksato.proxied
      }
      zksato_api = {
        hostname = cloudflare_dns_record.zksato_api.name
        content  = cloudflare_dns_record.zksato_api.content
        proxied  = cloudflare_dns_record.zksato_api.proxied
      }
      zksato_dash = {
        hostname = cloudflare_dns_record.zksato_dash.name
        content  = cloudflare_dns_record.zksato_dash.content
        proxied  = cloudflare_dns_record.zksato_dash.proxied
      }
    },
    var.zksato_alias_enabled ? {
      zksato_alias = {
        hostname = cloudflare_dns_record.zksato_alias[0].name
        content  = cloudflare_dns_record.zksato_alias[0].content
        proxied  = cloudflare_dns_record.zksato_alias[0].proxied
      }
      zksato_alias_api = {
        hostname = cloudflare_dns_record.zksato_alias_api[0].name
        content  = cloudflare_dns_record.zksato_alias_api[0].content
        proxied  = cloudflare_dns_record.zksato_alias_api[0].proxied
      }
      zksato_alias_dash = {
        hostname = cloudflare_dns_record.zksato_alias_dash[0].name
        content  = cloudflare_dns_record.zksato_alias_dash[0].content
        proxied  = cloudflare_dns_record.zksato_alias_dash[0].proxied
      }
    } : {}
  )
}

output "coin_dns_record" {
  description = "zCoin DNS record details."
  value = {
    hostname = cloudflare_dns_record.coin.name
    content  = cloudflare_dns_record.coin.content
    proxied  = cloudflare_dns_record.coin.proxied
  }
}

output "cloudflared_ingress" {
  description = "Ingress rules to merge into the cloudflared tunnel configuration."
  value = concat(
    local.ingress,
    [{ service = "http_status:404" }]
  )
}

output "phase6_urls" {
  description = "Phase 6 external readiness URLs derived from the api6 route."
  value = contains(keys(var.app_routes), "phase6") ? {
    ALERT_TEST_URL            = "https://${var.app_routes.phase6.hostname}/alerts/test"
    ALERT_DELIVERY_STATUS_URL = "https://${var.app_routes.phase6.hostname}/alerts/status"
    AI_UPLOAD_URL             = "https://${var.app_routes.phase6.hostname}/ai/upload"
    AI_FAILOVER_URL           = "https://${var.app_routes.phase6.hostname}/ai/failover"
    AI_STREAMING_URL          = "https://${var.app_routes.phase6.hostname}/ai/stream"
    GITHUB_WEBHOOK_URL        = "https://${var.app_routes.phase6.hostname}/webhooks/github"
    SESSION_PROVIDER_URL      = "https://${var.app_routes.phase6.hostname}/session/health"
    OBS_DASHBOARD_URL         = "https://${var.app_routes.phase6.hostname}/grafana/"
    OBS_TRACES_URL            = "https://${var.app_routes.phase6.hostname}/jaeger/"
  } : null
}
