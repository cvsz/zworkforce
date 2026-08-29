output "dns_records" {
  description = "Cloudflare DNS records managed by this stack."
  value = {
    for key, record in cloudflare_dns_record.app_routes : key => {
      hostname = record.name
      content  = record.content
      proxied  = record.proxied
    }
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
