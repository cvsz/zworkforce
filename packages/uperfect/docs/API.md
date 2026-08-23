# U.Perfect API Contract / สัญญา API

## ภาษาไทย

### Health and dashboard

- `GET /api/health` returns `{status, brand}`.
- `GET /api/dashboard` returns counts and secret-free integration summaries.
- `GET /api/integrations` returns provider, status, webhook path, and secret-free
  `label_th`/`label_en` plus `setup_note_th`/`setup_note_en` fields.

### Product and sales assets

- `GET /api/products?q=...` lists catalog facts.
- `POST /api/products` saves a validated product payload.
- `GET /api/sales-assets` returns validated TH/EN response assets and local media metadata.
- `GET /api/integration-guides` returns provider guide and approval-form links
  only; it never returns credentials.

### Conversation

`POST /api/messages` accepts:

```json
{
  "platform": "facebook",
  "customer_id": "customer-1",
  "text": "สนใจวิตซีโลเอ้"
}
```

The response contains conversation, reply, intent, automated flag, and active
product. `POST /api/conversations/{id}/takeover` accepts `{ "enabled": true }`.

### Orders

`POST /api/orders` creates an order only for an available priced product. Payment
evidence moves `awaiting_payment` to `pending_review`; transition to `confirmed`
requires a valid state transition and an actor.

### Webhook test boundary

`POST /api/webhooks/{provider}` accepts a normalized payload with `event_id`,
`customer_id`, and `text`. Trusted local tests must include:

```text
Facebook: X-Hub-Signature-256: sha256=<HMAC-SHA256 hex>
LINE: X-Line-Signature: <base64 HMAC-SHA256>
TikTok/Shopee normalized boundary: X-UPerfect-Webhook-Signature: sha256=<hex>
```

The HMAC covers the exact UTF-8 request body and uses the server-only provider
secret. Missing or invalid signatures return HTTP 401 with
`WEBHOOK_SIGNATURE_INVALID`. The endpoint is not a raw Facebook, TikTok,
Shopee, or LINE adapter; raw provider adapters must verify their own signature,
state, timestamps, and permissions before normalization.

`GET /api/notifications` exposes only pending/failed event metadata. A confirmed
order creates an outbox row; `app/worker.py` claims it with a lease and retries
transport failures when LINE is configured.

## English

- `GET /api/health`: process and brand health.
- `GET /api/dashboard`: counts and secret-free integration summaries.
- `GET /api/integrations`: provider status and bilingual setup notes, without
  credentials.
- `GET /api/products`: catalog facts and optional search.
- `GET /api/sales-assets`: validated bilingual response/media metadata.
- `GET /api/integration-guides`: TH/EN guide and approval-form links with no
  credentials.
- `POST /api/messages`: normalized conversation input and Autobot reply.
- `POST /api/conversations/{id}/takeover`: pause/resume automation.
- `POST /api/orders`: create a priced draft order.
- `POST /api/orders/{id}/payment-evidence`: submit evidence for review.
- `POST /api/orders/{id}/transition`: perform a guarded status transition.
- `GET /api/settings` and `PATCH /api/settings`: safe preferences only.
- `GET /api/notifications`: pending/failed outbox metadata without message
  credentials.
- `POST /api/webhooks/{provider}`: signed normalized local test boundary.

Provider raw payloads must not call the normalized route until an adapter has
validated provider-specific signatures, state, timestamps, and permissions.
