# U.Perfect API Onboarding and Integration Guide

**System:** U.Perfect Social Commerce OS
**Current mode:** Local-only at `192.168.74.130`
**Initial provider state:** `unconfigured`
**Approval owner:** The business account owner for each platform

This guide explains how to request API access from the official portals and
configure the server side of U.Perfect safely. A field in the Dashboard does
not prove a live connection. Never put tokens, secrets, PINs, or passphrases in
the browser, chat, Git, screenshots, or documentation.

Use the [Provider Access and Approval Form](PROVIDER-APPROVAL-FORM_EN.md) to
record only identifiers, scopes, callbacks, owners, and redacted evidence. The
form is not a credential store.

## 1. Common onboarding flow

1. The account owner signs in to the official provider portal.
2. Create the app/channel and request only the product and scopes required.
3. Register an HTTPS callback/webhook that the provider can reach.
4. Store credentials in the server environment or secret manager.
5. Test verification, event delivery, replies, and idempotency.
6. Check `GET /api/integrations` and the **Channels** view against the evidence.
7. Test with a sandbox or test account before production traffic.
8. Record expiry, owner, rotation, and revocation procedures internally.

### Local-only boundary

The current service binds to `192.168.74.130:18765` and uses the Ollama
endpoint at `http://192.168.74.130:11434` for local AI. External provider
credentials are not part of the local profile, and opening the Dashboard alone
must not change a provider to `configured`.

### Values that must remain server-side

Never place these values in frontend code, PWA cache, issues, pull requests,
screenshots, or commits:

- access tokens, refresh tokens, client secrets, partner keys, channel secrets
- webhook verify tokens used as shared secrets
- GPG PINs, passphrases, private keys, or credential files

<a id="facebook-messenger-meta"></a>
## 2. Facebook Messenger / Meta

### Official portals

- Messenger Platform overview: <https://developers.facebook.com/docs/messenger-platform/overview/>
- Webhooks: <https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks>
- Quick start: <https://developers.facebook.com/docs/messenger-platform/getting-started/quick-start/>

### Required inputs

- Meta Developer account and a Business meeting Meta's applicable requirements
- Meta App with the Messenger/Business use case enabled
- U.Perfect's Facebook Page and the required admin/developer role
- Page access token issued for that Page
- A server-generated webhook verify token kept private

### Steps

1. Open Meta for Developers and create an App suitable for Messenger/Business.
2. Add the Messenger product/use case.
3. Select `@spookyuperfect`, or the Page confirmed by the account owner.
4. Generate a Page access token in App Dashboard and store it as
   `FACEBOOK_PAGE_ACCESS_TOKEN`.
5. Generate a random server verify token and store it as
   `FACEBOOK_VERIFY_TOKEN`.
6. Register the HTTPS callback for the provider adapter and subscribe only to
   the required events, such as messages and postbacks.
7. Subscribe the Page to the App and confirm that the Page subscription works.
8. Send test messages from an approved test account and verify inbound,
   outbound, duplicate event, and human takeover behavior.
9. Complete App Review or Business Verification whenever Meta requires it for
   the requested access or production use.

### U.Perfect mapping

| Meaning | Environment | Notes |
| --- | --- | --- |
| Page access token | `FACEBOOK_PAGE_ACCESS_TOKEN` | secret; server-only |
| Webhook verify token | `FACEBOOK_VERIFY_TOKEN` | shared secret; server-only |
| Page URL | workspace `facebook_page_url` | reference only, not proof of connection |

### U.Perfect gate

The current local test route is `POST /api/webhooks/facebook`. It accepts a
normalized payload such as `event_id`, `customer_id`, and `text` only with
`X-Hub-Signature-256: sha256=<hex>` over the raw body using
`FACEBOOK_APP_SECRET`. This is not a raw Meta adapter; build and verify that
server-side adapter before accepting real Meta traffic.

<a id="tiktok-shop-open-platform"></a>
## 3. TikTok Shop Open Platform

### Official portals

- Create an app in Partner Center: <https://partner.tiktokshop.com/docv2/page/create-your-app>
- OAuth client: <https://partner.tiktokshop.com/docv2/page/create-tts-app-oauth-client>
- Authorization guide: <https://partner.tiktokshop.com/docv2/page/authorization-guide-202309>
- Authorization overview/review: <https://partner.tiktokshop.com/docv2/page/authorization-overview-202407>
- Developer guide: <https://partner.tiktokshop.com/docv2/page/tts-developer-guide>
- Webhook configuration: <https://partner.tiktokshop.com/docv2/page/configuration-guide>
- Check the current Partner Center region/authorization label for Thailand/ROW.

### Required inputs

- TikTok Shop Partner Center account
- An app/service approved for the shop and required API products
- `service_id`, `app_key`, and `app_secret`
- Seller/shop authorization and an authorization code
- A registered callback URL
- A refresh token stored on the server

### Steps

1. Create the app in Partner Center and select only the required shop, order,
   and customer communication API products/scopes.
2. Record `service_id`, `app_key`, and the generated `app_secret` in the
   server-side secret system.
3. Have the seller authorize the shop using the authorization URL shown by
   Partner Center for the account's region, such as ROW/Thailand.
4. Receive the short-lived `auth_code` on the registered callback without
   writing it to logs.
5. Exchange the code at the TikTok Shop Open Platform token endpoint and store
   the access and refresh tokens server-side.
6. Configure the webhook in Developing/Basic information using HTTPS/TLS 1.2
   and a provider-supported domain. Follow the portal's current restriction on
   IP addresses and ports.
7. Validate the provider Authorization header/signature and respond with the
   required HTTP status within the provider's time limit before normalizing the
   event.
8. Test refresh, rate limits, duplicate events, failed delivery, and human
   takeover with the test shop.

### Token flow to preserve

- The current authorization guide documents a 30-minute, single-use
  authorization code; re-check the portal if that policy changes.
- The access token is scoped to the approved API calls.
- The refresh token is used to obtain a new access token and must be rotated
  and stored securely.
- The current TikTok Shop documentation lists
  `https://auth.tiktok-shops.com/api/v2/token/get` and
  `https://auth.tiktok-shops.com/api/v2/token/refresh`; confirm the market/API
  version in Partner Center before calling them.
- Never hard-code a token in source code or the Settings page.

### U.Perfect mapping

| Meaning | Environment | Notes |
| --- | --- | --- |
| App key | `TIKTOK_APP_KEY` | identifier; server-side config |
| App secret | `TIKTOK_APP_SECRET` | secret; server-only |
| Refresh token | `TIKTOK_REFRESH_TOKEN` | secret; server-only |

If an OAuth callback adapter is added, use the redirect URL registered in the
portal and keep callback configuration in deployment config, never in the
frontend.

### U.Perfect gate

`POST /api/webhooks/tiktok` is currently a normalized local test boundary. It
requires `X-UPerfect-Webhook-Signature: sha256=<hex>` over the raw body using
`TIKTOK_WEBHOOK_SECRET` and an `event_id` for idempotency. Do not connect raw
TikTok webhook payloads directly to this route.

<a id="shopee-open-platform"></a>
## 4. Shopee Open Platform

### Official portals

- Shopee Open Platform: <https://open.shopee.com/>
- Partner API host used by integration setups: <https://partner.shopeemobile.com/>

Portal labels, scopes, and approval steps can vary by country and API version.
Use the console and documentation presented to the shop owner on the day of
setup.

### Required inputs

- Shopee Open Platform/Partner account
- Partner ID and Partner Key
- Shop ID to authorize
- A callback URL and authorization code from the current portal flow
- The access/refresh values required by the current API version
- API permissions covering orders, items, and customer service/chat if chat is
  required

### Steps

1. Sign in to Open Platform with the approved partner account.
2. Create an application and select the shop's country/region.
3. Store Partner ID as `SHOPEE_PARTNER_ID` and Partner Key as
   `SHOPEE_PARTNER_KEY` in the server secret store only.
4. Register the callback and have the seller authorize the Shop ID.
5. Receive the authorization code and shop identifier on a callback that checks
   state.
6. Exchange the code using the current API version and store the resulting
   token server-side.
7. Create request signatures according to each endpoint's current rules and
   validate timestamps/expiry.
8. Request only the required scopes, especially customer service/chat when
   that is separate from order/item access.
9. Test shop authorization, order read, chat send/receive, rate limits, and
   duplicate events in a test shop.

### U.Perfect mapping

| Meaning | Environment | Notes |
| --- | --- | --- |
| Partner ID | `SHOPEE_PARTNER_ID` | identifier |
| Partner Key | `SHOPEE_PARTNER_KEY` | secret; server-only |
| Shop ID | `SHOPEE_SHOP_ID` | account scope; confirm with owner |

### U.Perfect gate

`POST /api/webhooks/shopee` is a normalized local test boundary. It requires
`X-UPerfect-Webhook-Signature: sha256=<hex>` over the raw body using
`SHOPEE_WEBHOOK_SECRET` and event idempotency. The release does not claim that a
Shopee chat/order adapter is production-ready.

<a id="line-messaging-api"></a>
## 5. LINE Messaging API

### Official portals

- Building a bot: <https://developers.line.biz/en/docs/messaging-api/building-bot/>
- Channel access token: <https://developers.line.biz/en/docs/basics/channel-access-token/>
- Messaging API reference: <https://developers.line.biz/en/reference/messaging-api/>

### Current release scope

U.Perfect contains a retryable notification outbox for confirmed-order events
to LINE and a normalized inbound boundary that verifies `X-Line-Signature` over
the raw body with `LINE_CHANNEL_SECRET`. It does not claim a production inbound
LINE chatbot adapter. Do not use `LINE_CHANNEL_ACCESS_TOKEN` for automated
customer replies until the official adapter and account verification are ready.

### LINE Developers July 2026 compatibility note

Reviewed on 2026-08-10 against the [LINE Developers July 2026 news index](https://developers.line.biz/en/news/2026/07):

- [LIFF v2.29.2 (2026-07-31)](https://developers.line.biz/en/news/2026/07/31/release-liff-2-29-2/)
  was released without feature changes. U.Perfect does not use LIFF in this
  release, so no runtime configuration changes are required.
- [Rich menu statistics (2026-07-01)](https://developers.line.biz/en/news/2026/07/01/rich-menu-insight/)
  and [LINE MINI App in-app purchase updates](https://developers.line.biz/en/news/2026/07/01/iap-service-fees/)
  are outside the current product scope. U.Perfect has no rich-menu analytics,
  LINE MINI App, or LINE in-app purchase integration in this release.
- The [2026-07-28 LINE Platform incident](https://developers.line.biz/en/news/2026/07/28/messaging-api-outage/)
  was resolved. A future LINE sender must retain outbox idempotency and apply
  LINE's documented `X-Line-Retry-Key` handling for retryable 5xx/timeouts where
  the endpoint supports it; it must not blindly duplicate customer messages.

These notes are compatibility guidance, not evidence that a LINE account is
configured or verified. Re-check the official news index and API reference
before enabling a new LINE product or transport.

### Outbound notification steps

1. Create a Messaging API channel in LINE Developers Console.
2. Add the Official Account and identify the authorized recipient.
3. Issue a channel access token with a suitable lifetime and rotation plan.
4. Store it as `LINE_CHANNEL_ACCESS_TOKEN`.
5. Store the user/group/room destination as `LINE_ADMIN_DESTINATION`.
6. Test a server-side push and confirm that the outbox changes from pending to
   sent, or remains failed and retryable on transport failure.
7. Alert on revoked tokens, invalid destinations, or rising failed events.

### Future inbound steps

1. Create/check `LINE_CHANNEL_SECRET` in the server secret system.
2. Register an HTTPS webhook URL in LINE Developers Console.
3. Verify the endpoint and enable **Use webhook**.
4. Validate `x-line-signature` with the channel secret before normalization.
5. Validate reply-token lifetime and use the reply/push endpoints for the event.

### U.Perfect mapping

| Meaning | Environment | Current status |
| --- | --- | --- |
| Channel access token | `LINE_CHANNEL_ACCESS_TOKEN` | outbox when owner configures it |
| Admin destination | `LINE_ADMIN_DESTINATION` | outbox |
| Channel secret | `LINE_CHANNEL_SECRET` | HMAC for normalized/inbound boundary; server-only |

## 6. Verification after setup

### Dashboard

1. Open **Channels**.
2. Select the provider and read its setup note.
3. Open the TH or EN provider guide from the provider card.
4. Confirm that the browser shows no token or secret.
5. Switch the Dashboard language without changing secret configuration.

### API

```bash
curl http://192.168.74.130:18765/api/health
curl http://192.168.74.130:18765/api/integrations
curl http://192.168.74.130:18765/api/integration-guides
curl http://192.168.74.130:18765/api/sales-assets
```

`configured` means the required environment values are present. It does not
prove that a token works. A provider ping, webhook delivery, permission check,
and test transaction are required before a provider should be considered
`verified`.

## 7. Production approval checklist

- [ ] Account owner approved the app and scopes.
- [ ] Callback/webhook uses HTTPS and the correct registered domain.
- [ ] Tokens/secrets live in a server secret store, not Git.
- [ ] Provider signature/state/nonce validation runs server-side.
- [ ] Duplicate events are ignored safely.
- [ ] Rate limits and retry/backoff have test evidence.
- [ ] Human takeover and automation stop behavior are tested.
- [ ] Payment evidence stays `pending_review` until an authorized reviewer acts.
- [ ] LINE outbox has an owner and token rotation plan.
- [ ] Rollback/revocation contacts and the activation timestamp are recorded.

## 8. Detailed approval workbook

Complete the [Provider Access and Approval Form](PROVIDER-APPROVAL-FORM_EN.md)
for every provider to be enabled. Record the owner, region, app/channel ID,
scope list, exact callback/webhook URLs, review/ticket evidence, test evidence,
and rollback owner. The workbook deliberately separates `configured` (the
environment is complete) from `verified` (provider delivery and server-side
verification are evidenced).

### Local-only callback boundary

`192.168.74.130` is the local runtime and normalized test host. An external
provider must not call a private LAN IP directly. Before production enablement,
provide a public HTTPS adapter that validates provider signatures, OAuth
state/nonce, timestamps, retries, and duplicate events before forwarding into
the internal system.
