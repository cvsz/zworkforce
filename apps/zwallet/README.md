# ZWallet Adapter

This app is an audited billing adapter boundary for Z Platform.

It forwards credits and invoice-intent requests to `services/billing-ledger` only. It does not include wallet signing, swaps, cards, KYC, MPC, private keys, or payment-provider credentials.

## Runtime

- `GET /health` reports adapter status and explicitly confirms no wallet/card authority.
- `POST /api/invoice-intents` forwards invoice intent creation to Billing Ledger.
- `POST /api/credits` currently returns HTTP 503 and never calls Billing Ledger; the absolute credit setter stays disabled until a separately reviewed append-only adjustment and durable idempotency contract is implemented.

## Required environment

- `Z_PLATFORM_BILLING_LEDGER_URL`
- `Z_PLATFORM_BILLING_LEDGER_SERVICE_TOKEN` (dedicated adapter-to-ledger credential; never returned to callers)
- `Z_PLATFORM_BILLING_ADAPTER_ENABLE_MUTATIONS` (must remain unset/false until the trusted gateway contract is verified)
- `Z_PLATFORM_TENANT_ASSERTION_SECRET` (high-entropy secret shared only by the trusted gateway and adapter)

`Z_PLATFORM_SERVICE_TOKEN` is not accepted as a fallback. Provision the dedicated value independently in the adapter and ledger secret stores, restricted to this service boundary. For rotation, provision the new value to both workloads, verify new-token acceptance, then revoke the old value and verify old-token rejection. Source changes do not rotate production secrets.\n\n## Tenant admission and mutation safety

Billing mutations are denied by default. The adapter requires `Z_PLATFORM_BILLING_ADAPTER_ENABLE_MUTATIONS=true`, a valid tenant-assertion secret of at least 32 UTF-8 bytes, and a signed, time-bounded tenant assertion from the trusted gateway. Missing configuration returns HTTP 503; invalid or mismatched assertions return HTTP 403. No request is forwarded to Billing Ledger unless these checks pass.

Invoice-intent requests accept only `tenant_id`, `idempotency_key`, `currency`, and `amount_minor`. Any unknown top-level field is rejected before forwarding; arbitrary metadata and unrecognized financial/identity fields are not part of the audited contract. The `currency` value must be a three-letter alphabetic code and `amount_minor` must be a positive safe integer; invalid object/array values are rejected before any upstream request.

For each POST, the trusted gateway must send:

- `X-Authenticated-Tenant`: the authorized tenant ID
- `X-Tenant-Assertion-Timestamp`: Unix epoch seconds (10 digits)
- `X-Tenant-Assertion-Signature`: lowercase hexadecimal HMAC-SHA256

The signature is calculated over this exact UTF-8 canonical string using `Z_PLATFORM_TENANT_ASSERTION_SECRET`:

```text
<tenant_id>
<timestamp>
POST
<exact_path>
<idempotency_key>
<body_sha256_hex>
```

Each line is separated by exactly one line-feed (`LF`, U+000A). `<body_sha256_hex>` is the lowercase SHA-256 digest of the exact UTF-8 HTTP body bytes sent to the adapter. The gateway must sign the same bytes it forwards; it must not parse and reserialize the body between signing and forwarding. The signature must not include literal backslash and `n` characters.

Each line is separated by exactly one line-feed (`LF`, U+000A). The signature must not include literal backslash and `n` characters.

The exact path is `/api/invoice-intents` or `/api/credits`. The timestamp must be within 60 seconds of adapter time. The adapter compares signatures in constant time and forwards a newly constructed `X-Authenticated-Tenant` header only after verification; it does not trust a caller-supplied tenant header by itself. The gateway must keep the assertion secret private and restrict network access so untrusted clients cannot call the adapter directly.

Generate the assertion secret with a cryptographically secure random generator. Do not store it in source control, logs, images, issue comments or command-line arguments. Keep mutations disabled until the gateway signer, secret distribution, network policy and deployed tenant-isolation tests have been independently reviewed. The adapter enforces this boundary in code: `POST /api/credits` always fails closed with HTTP 503 and does not contact Billing Ledger until a separately reviewed append-only adjustment/idempotency implementation replaces the disabled handler.

## Production transport

When `NODE_ENV=production`, the Billing Ledger URL must use HTTPS. Malformed URLs, unsupported schemes, embedded URL credentials, query strings, fragments, or plaintext HTTP are treated as unavailable and fail closed before sending the service token. HTTP is permitted only outside production for local/test environments.

## Failure and retry contract

- The adapter returns HTTP 503 with a generic body when Billing Ledger is unavailable, times out/connects unsuccessfully, returns 3xx redirects, 401/403 upstream authentication failures, 408 timeouts, 429 or 5xx responses, is not configured, or returns invalid success JSON. Redirects are never followed for financial mutations.
- Responses include `Cache-Control: no-store`. The adapter does not retry automatically and does not forward upstream error bodies or `Retry-After`.
- A 503 does **not** prove whether a financial mutation committed. Reconcile with Billing Ledger using the same durable, operation-specific `idempotency_key` before retrying; never generate a new key solely because the response was 503.
- Upstream request-validation and conflict responses remain HTTP 400 with a generic message. Upstream authentication/configuration and timeout failures map to HTTP 503. Forbidden wallet/card/KYC/MPC/swap payloads remain rejected.

## Validation

Run `npm test` to verify the adapter rejects wallet signing, card, KYC, MPC, and swap payloads and preserves the retryable 503 contract.


## Resource limits and timeouts
- The adapter accepts JSON object request bodies up to 64 KiB; larger bodies return HTTP 413 before any Billing Ledger request.
- Billing Ledger calls use a 5-second timeout by default. Operators may set `Z_PLATFORM_BILLING_LEDGER_TIMEOUT_MS` to an integer from 100 through 30000. Invalid values fail closed with HTTP 503.
- A timeout returns the same generic, non-cacheable HTTP 503 as other upstream availability failures. It does not prove whether a financial mutation committed; reconcile with the same durable idempotency key before retrying.
