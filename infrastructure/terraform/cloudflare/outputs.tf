output "moopiew_url" {
  value       = "https://${var.moopiew_hostname}"
  description = "Public Moopiew preorder URL after the DNS record and tunnel ingress are active."
}

output "arin_url" {
  value       = "https://${var.arin_hostname}"
  description = "Public Arin URL after the proxied DNS record and tunnel ingress are active."
}

output "zttshop_url" {
  value       = "https://${var.zttshop_hostname}"
  description = "Public zttshop URL after the proxied DNS record and tunnel ingress are active."
}

output "qwen_url" {
  value       = "https://${var.qwen_hostname}"
  description = "Public Qwen chat URL after the proxied DNS record and tunnel ingress are active."
}

output "chat_url" {
  value       = "https://${var.chat_hostname}"
  description = "Public OpenWebUI chat URL after the proxied DNS record and tunnel ingress are active."
}

output "piewdash_url" {
  value       = "https://${var.piewdash_hostname}"
  description = "Public engineering dashboard URL."
}

output "zerp_url" {
  value       = "https://${var.zerp_hostname}"
  description = "Public zERP URL after the proxied DNS record and tunnel ingress are active."
}

output "cmeerp_url" {
  value       = "https://${var.cmeerp_hostname}"
  description = "Public CME Pro ERP URL after the proxied DNS record and tunnel ingress are active."
}

output "zai_url" {
  value       = "https://${var.zai_hostname}"
  description = "Public ZEAZ AI Command Center URL after proxied DNS record and tunnel ingress are active."
}

output "auth_url" {
  value       = "https://${var.auth_hostname}"
  description = "Public ZEAZ Authentication Portal URL after proxied DNS record and tunnel ingress are active."
}

output "piewdash_access_audience" {
  value       = cloudflare_zero_trust_access_application.piewdash.aud
  description = "Audience claim expected on Cloudflare Access JWTs for the dashboard."
}

output "laps_url" {
  value       = "https://${var.laps_hostname}"
  description = "Public LAPS URL after the proxied DNS record and tunnel ingress are active."
}

output "cloudflared_ingress" {
  value = concat(
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
      { hostname = var.auth_hostname, service = var.auth_origin },
      { hostname = var.laps_hostname, service = var.laps_origin },
    ],
    local.zworkforce_ingress,
    local.zeaz_one_ingress,
    [{ service = "http_status:404" }],
  )
  description = "Ingress fragment to merge before the terminal fallback of a locally managed tunnel."
}
