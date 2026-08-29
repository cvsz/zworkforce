#!/usr/bin/env bash
set -euo pipefail

# ตรวจสอบว่า Secrets ครบถ้วนหรือไม่
required_secrets=(
  "ALERT_TEST_URL"
  "AI_PROVIDER_ENDPOINTS"
  "BROWSER_BUNDLE_BASE64"
)

for secret in "${required_secrets[@]}"; do
  if [[ -z "${!secret:-}" ]]; then
    echo "::error::Missing required secret: $secret"
    exit 1
  fi
done

# ตรวจสอบ URL ว่าไม่ใช่ Placeholder
if [[ "$ALERT_TEST_URL" =~ (localhost|example\.com|127\.0\.0\.1) ]]; then
  echo "::error::ALERT_TEST_URL contains forbidden placeholder hostname"
  exit 1
fi

# ตรวจสอบ AI Providers (ต้องมีอย่างน้อย 2)
IFS=',' read -ra PROVIDERS <<< "$AI_PROVIDER_ENDPOINTS"
if (( ${#PROVIDERS[@]} < 2 )); then
  echo "::error::AI_PROVIDER_ENDPOINTS must contain at least 2 distinct endpoints"
  exit 1
fi

echo "✅ All automated gate checks passed."
exit 0