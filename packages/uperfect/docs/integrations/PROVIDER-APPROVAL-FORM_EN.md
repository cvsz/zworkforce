# Provider Access and Approval Form / U.Perfect

This is an **identity and evidence worksheet** for the business owner of
Facebook/Meta, TikTok Shop, Shopee, or LINE. Use it in an internal system or a
private GitHub issue only. Never put tokens, secrets, PINs, passphrases,
payment QR data, or credential files in this form.

## How to use it

1. The account owner fills in the identity fields and selects the provider.
2. Complete the work in the official provider portal with the business owner
   account.
3. Attach only portal URLs, review/ticket IDs, redacted screenshots, and
   timestamps. Never attach secret values.
4. The developer places secrets in the server environment and runs the
   acceptance checklist.
5. Use `unconfigured` until required environment values exist. Use
   `configured` only for environment completeness, and `verified` only after
   provider tests have evidence.

## Current release boundary

- U.Perfect local runtime: `http://192.168.74.130:18765`
- Local AI: `http://192.168.74.130:11434` with `zCoder:latest`
- Initial provider state: `unconfigured`
- `POST /api/webhooks/{provider}` is a normalized local test boundary protected
  by HMAC over the raw body.
- Do not use `192.168.74.130` as an external provider callback/webhook. It is a
  private LAN address; an external provider needs a public HTTPS adapter with a
  trusted certificate and provider-signature verification.
- Having `uperfect.zeaz.dev` or opening the Dashboard is not proof of provider
  approval or a live connection.

## 1. Business owner and shared request

| Field | Value |
| --- | --- |
| Company/store | <!-- fill in --> |
| Approving owner | <!-- fill in --> |
| Business email | <!-- fill in --> |
| Technical owner | <!-- fill in --> |
| Request date | <!-- YYYY-MM-DD --> |
| Desired enablement date | <!-- YYYY-MM-DD --> |
| Country/market | Thailand / other: <!-- fill in --> |
| Environment | sandbox / test shop / production |
| Provider | Facebook / TikTok / Shopee / LINE |
| Goal | receive messages / reply / read orders / LINE notification |

### Scope discipline

- Request only scopes required by the selected workflow.
- Separate message read, message send, order read, fulfillment, and
  post/comment permissions.
- Record the exact scope names shown by the current portal; do not infer names
  from an old guide.
- Write a business reason for every requested scope for the review process.

| Scope/API product | Business reason | Required for this release |
| --- | --- | --- |
| <!-- exact portal name --> | <!-- fill in --> | yes / no |
| <!-- exact portal name --> | <!-- fill in --> | yes / no |

## 2. Callback, webhook, and security gate

| Field | Approved/verified value |
| --- | --- |
| Public HTTPS adapter URL | <!-- never use a LAN IP --> |
| OAuth redirect/callback URL | <!-- exact URL including path --> |
| Provider webhook URL | <!-- exact URL including path --> |
| TLS certificate owner/expiry | <!-- fill in --> |
| Provider signature verification implemented | yes / no |
| OAuth state/nonce validation implemented | yes / no / not applicable |
| Event idempotency key | <!-- provider event ID --> |
| Retry/backoff and rate-limit plan | <!-- runbook link --> |
| Raw payload retention policy | <!-- retention/deletion rule --> |

The current `POST /api/webhooks/{provider}` endpoint accepts only a normalized
test payload with the provider-specific HMAC header from a server-side test. Do
not send raw provider payloads to this route.

<a id="facebook-messenger-meta"></a>
## 3. Facebook Messenger / Meta

### Official portals and form fields

- Portal: <https://developers.facebook.com/>
- Messenger overview: <https://developers.facebook.com/docs/messenger-platform/overview/>
- Quick start: <https://developers.facebook.com/docs/messenger-platform/getting-started/quick-start/>
- Webhooks: <https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks>

| Field | Non-secret value |
| --- | --- |
| Meta Business name/ID | <!-- identifier --> |
| Meta App name/ID | <!-- identifier --> |
| App mode | Development / Live |
| Messenger use case/product | <!-- portal label --> |
| Facebook Page name/ID | `@spookyuperfect` / <!-- Page ID --> |
| Page owner/admin confirmed | yes / no |
| Requested permissions | <!-- exact portal names --> |
| App Review/Business Verification case | <!-- URL or case ID --> |
| Test accounts/Page roles | <!-- no passwords --> |
| Callback/webhook URL | <!-- exact public HTTPS URL --> |

### Approval steps

1. The business owner signs in to Meta for Developers and selects the correct
   Business and App.
2. Add the Messenger use case/product shown by the current portal.
3. Connect Page `@spookyuperfect` and confirm the required admin/developer role.
4. Record App ID, Business ID, Page ID, and permission names in this form.
5. Register the HTTPS callback/webhook of an adapter that verifies requests
   server-side. Do not point Meta at `192.168.74.130`.
6. Test with Page roles first, then complete App Review or Business Verification
   when Meta requires production access or the requested permissions.
7. After approval, the server owner issues the Page access token and stores it
   only as `FACEBOOK_PAGE_ACCESS_TOKEN`. Generate a server-side verify token
   stored only as `FACEBOOK_VERIFY_TOKEN`.

### Evidence to attach, with secrets removed

- App/Business/Page identifiers
- Approved permission list and expiry if applicable
- Review case/status URL or redacted screenshot
- Webhook verification and inbound/outbound test IDs
- Duplicate-event and human-takeover test results

### Environment mapping

| Portal value | U.Perfect environment | Never expose in |
| --- | --- | --- |
| Page access token | `FACEBOOK_PAGE_ACCESS_TOKEN` | browser, GitHub, logs |
| Server-generated verify token | `FACEBOOK_VERIFY_TOKEN` | browser, GitHub, logs |
| Page URL/reference | `facebook_page_url` workspace setting | reference only |

<a id="tiktok-shop-open-platform"></a>
## 4. TikTok Shop Open Platform

### Official portals and form fields

- Partner Center: <https://partner.tiktokshop.com/>
- Create an app: <https://partner.tiktokshop.com/docv2/page/create-your-app>
- OAuth client: <https://partner.tiktokshop.com/docv2/page/create-tts-app-oauth-client>
- Authorization guide: <https://partner.tiktokshop.com/docv2/page/authorization-guide-202309>
- Authorization overview: <https://partner.tiktokshop.com/docv2/page/authorization-overview-202407>
- Webhook configuration: <https://partner.tiktokshop.com/docv2/page/configuration-guide>

| Field | Non-secret value |
| --- | --- |
| Partner Center account/organization | <!-- identifier --> |
| App type | Public / Custom |
| Market/region | Thailand / ROW / <!-- portal value --> |
| App/service name | <!-- fill in --> |
| `service_id` | <!-- identifier --> |
| `app_key` | <!-- identifier --> |
| API products/scopes | <!-- exact portal names --> |
| Development shop/test seller | <!-- identifier --> |
| Seller/shop authorization | requested / approved |
| Redirect URL | <!-- exact registered URL --> |
| Webhook URL | <!-- public HTTPS domain; never LAN IP --> |
| Enrollment/review case | <!-- case ID/status URL --> |

### Approval and OAuth steps

1. Register the developer/Partner Center account and select the market that
   matches the Thailand seller.
2. Create an app/service, choose Public or Custom, and request only the API
   products/scopes required for the shop workflow.
3. Record `service_id` and `app_key`; do not put `app_secret` in this form.
4. Register an exact-match redirect URL and prepare an HTTPS adapter that
   validates OAuth `state`/nonce.
5. Use the authorization link generated by Partner Center so the seller can
   authorize the shop.
6. Receive the short-lived, one-time `auth_code` at the callback and exchange
   it server-side. The current authorization guide documents a 30-minute
   lifetime; re-check the Partner Center policy before production. Never log or
   paste the code into chat.
7. Store the app key/secret and refresh token in the server environment using
   the mapping below.
8. Configure the webhook under the current Developing/Basic information flow,
   obey HTTPS/TLS requirements, and verify the provider authorization/signature
   before normalizing events.
9. Complete scope/enrollment/app review evidence required by the public-app or
   connector flow before production enablement.

### Environment mapping

| Portal value | U.Perfect environment | Note |
| --- | --- | --- |
| App key | `TIKTOK_APP_KEY` | server-side identifier |
| App secret | `TIKTOK_APP_SECRET` | secret; never in docs |
| Refresh token | `TIKTOK_REFRESH_TOKEN` | secret; rotate per portal |
| Registered redirect URL | adapter deployment config | absent from local-only normalized release |

### Evidence to attach

- App type, market, `service_id`, `app_key`, and scope list
- Test shop/seller authorization result
- Redirect/webhook verification result
- Enrollment/review status or ticket ID
- Masked token exchange/refresh test with status and expiry only
- Rate-limit, duplicate-event, and failed-delivery tests

<a id="shopee-open-platform"></a>
## 5. Shopee Open Platform

### Official portals and form fields

- Open Platform: <https://open.shopee.com/>
- Partner API host/reference: <https://partner.shopeemobile.com/>
- Follow the current documentation and menu labels shown for the account's
  region and API version.

| Field | Non-secret value |
| --- | --- |
| Partner organization/account | <!-- identifier --> |
| App name/ID | <!-- identifier if shown --> |
| Region/country | Thailand / <!-- portal value --> |
| Partner ID | <!-- identifier --> |
| Shop ID(s) | <!-- identifier --> |
| Requested API modules | order / item / chat / fulfillment / other |
| Requested scopes | <!-- exact portal names --> |
| Shop owner authorization | requested / approved |
| Redirect/callback URL | <!-- exact registered URL --> |
| Webhook URL | <!-- public HTTPS adapter URL --> |
| API version | <!-- portal value --> |
| Review/ticket status | <!-- ID/URL --> |

### Approval and request-signing steps

1. The owner signs in to Shopee Open Platform with the correct partner account.
2. Create the application for the shop's region/country and read the modules
   currently available to the account.
3. Record Partner ID, Shop ID, and scope names; never put the Partner Key in
   this form.
4. Register an exact-match callback and have the shop owner authorize the Shop
   ID.
5. Use the authorization-code/token flow documented for the current API version.
6. Store Partner ID/Key and any tokens in the server environment only.
7. Implement the endpoint-specific HMAC/request signature and validate the
   timestamp/expiry in the provider adapter before normalization.
8. Request only modules used by the workflow, such as order/item or customer
   service chat. Record separate chat approval if the portal requires it.
9. Test order read, item read, chat send/receive, rate limits, and duplicate
   events in a test shop before production.

### Environment mapping

| Portal value | U.Perfect environment | Note |
| --- | --- | --- |
| Partner ID | `SHOPEE_PARTNER_ID` | identifier |
| Partner Key | `SHOPEE_PARTNER_KEY` | secret; never in docs |
| Shop ID | `SHOPEE_SHOP_ID` | shop scope; owner must confirm |
| Registered redirect URL | adapter deployment config | absent from local-only normalized release |

### Evidence to attach

- Partner/app/region/API version identifiers
- Shop authorization result and scope list
- Callback/webhook verification result
- Masked API health/signature test and response status
- Order/item/chat evidence without customer data or secrets
- Rate-limit, retry, duplicate-event, and revoke/rotate runbook

<a id="line-messaging-api"></a>
## 6. LINE Messaging API

### Official portals and form fields

- Build a bot: <https://developers.line.biz/en/docs/messaging-api/building-bot/>
- Channel access token: <https://developers.line.biz/en/docs/basics/channel-access-token/>
- Receive webhooks: <https://developers.line.biz/en/docs/messaging-api/receiving-messages/>
- API reference: <https://developers.line.biz/en/reference/messaging-api/>

| Field | Non-secret value |
| --- | --- |
| LINE Developers provider | <!-- identifier/name --> |
| Messaging API channel name/ID | <!-- identifier --> |
| Official Account name/ID | <!-- identifier --> |
| Token type | v2.1 / stateless / short-lived / long-lived |
| Token expiry/rotation owner | <!-- fill in --> |
| Admin destination type | user / group / room |
| Admin destination ID | <!-- identifier; not a token --> |
| Inbound webhook URL (future) | <!-- public HTTPS adapter --> |
| Verify result / Use webhook | pending / success / enabled |
| Review/ticket status | <!-- fill in --> |

### Outbound notification steps

1. Create a Messaging API channel in LINE Developers Console and connect the
   correct Official Account.
2. Issue a channel access token with an expiry/type suitable for rotation; LINE
   recommends channel access token v2.1 for Messaging API use.
3. Store it server-side as `LINE_CHANNEL_ACCESS_TOKEN`.
4. Obtain the authorized user/group/room destination through the approved flow
   and store it as `LINE_ADMIN_DESTINATION`; do not guess it from a display name.
5. Test an internal push message and inspect the LINE notification outbox.
6. Record the rotation/revocation owner. Revoke immediately if the token is
   suspected to be compromised.

### Future inbound steps

1. Register a public HTTPS webhook with a certificate trusted by general
   browsers.
2. Enter the exact URL in the Messaging API tab, click Verify, and enable
   **Use webhook** only after verification succeeds.
3. Store the channel secret in the server secret system and validate
   `x-line-signature` before normalizing an event.
4. Add the Official Account as a friend to test follow/message events.
5. Disable Greeting/Auto-reply in LINE Official Account Manager when the
   Messaging API owns responses, preventing duplicate replies.

### Environment mapping and current scope

| Portal value | U.Perfect environment | Status |
| --- | --- | --- |
| Channel access token | `LINE_CHANNEL_ACCESS_TOKEN` | outbound outbox after owner setup |
| Admin destination | `LINE_ADMIN_DESTINATION` | outbound outbox |
| Channel secret | `LINE_CHANNEL_SECRET` | HMAC for inbound boundary; server-only |

This release does not enable inbound LINE chatbot delivery and does not claim
that LINE sends are live until the token, destination, sender transport, and
test evidence are complete.

## 7. Final approval and sign-off

| Gate | Owner | Evidence/link | Status |
| --- | --- | --- | --- |
| Portal account ownership | <!-- name --> | <!-- URL/case --> | pending |
| App/channel created | <!-- name --> | <!-- identifier --> | pending |
| Scope approved | <!-- name --> | <!-- review evidence --> | pending |
| Redirect/webhook verified | <!-- name --> | <!-- test evidence --> | pending |
| Server environment configured | <!-- name --> | <!-- deploy ID, no secret --> | pending |
| Provider API test passed | <!-- name --> | <!-- masked test ID --> | pending |
| Duplicate/retry/rate-limit test | <!-- name --> | <!-- runbook --> | pending |
| Human takeover tested | <!-- name --> | <!-- conversation test ID --> | pending |
| Rollback/revoke owner assigned | <!-- name --> | <!-- runbook --> | pending |

### Owner declaration

I confirm that the accounts and permissions listed above are authorized for
the business, scopes are limited to the required workflow, callbacks/webhooks
are verified, and secrets will be delivered only through the designated server
configuration channel.

- Approving owner: <!-- fill in -->
- Date/time UTC: <!-- fill in -->
- Signature or approval ticket: <!-- fill in -->
- Technical reviewer: <!-- fill in -->
- Verification date: <!-- fill in -->

Never set `verified` from a completed form alone. Provider delivery and
server-side verification evidence are required by the release checklist.
