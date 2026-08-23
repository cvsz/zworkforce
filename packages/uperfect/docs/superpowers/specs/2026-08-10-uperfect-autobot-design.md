# U.Perfect Social Commerce Autobot Design

**Status:** Approved by the supplied `rewrite-uperfect.md` execution brief; consolidated on 2026-08-10.

## Goal

Build a runnable U.Perfect Social Commerce OS that lets staff manage a product
catalogue, automate safe sales conversations, create and track orders, take
over conversations, receive LINE notifications, and prepare verified
integrations for Facebook Messenger, TikTok Shop, and Shopee.  The admin client
must work as an installable responsive web application on Android, iOS, and
Windows.  A real channel is shown as connected only after its credentials and
webhook verification have succeeded.

## Why this design

The export combines aspirational diagrams, static mockups, and invented
credential examples.  It does not contain a source application or usable
third-party credentials.  The build therefore delivers the complete local
product core and explicit integration boundaries rather than reproducing a
dashboard that incorrectly claims a live connection.

## Architecture

```text
Responsive installable web client
             | HTTPS JSON API
FastAPI application
  |-- catalog and product-memory service
  |-- conversation and automation service
  |-- order and payment-review service
  |-- platform/webhook adapter boundary
  |-- LINE notification outbox
  `-- audit and health endpoints
             |                 |
SQLite (local/test)       PostgreSQL + Redis (production configuration)
```

The application is a Python FastAPI backend with a dependency-free browser
client.  SQLite makes the complete system runnable in this checkout; the data
repository and session-store interfaces accept a PostgreSQL/Redis deployment
without changing HTTP contracts.  The client is a Progressive Web App (PWA),
which provides one installable codebase for Android, iOS, and Windows browsers
without a native toolchain or a second implementation.

## Components and responsibilities

### Backend API

`app/main.py` owns application construction, lifecycle, static-file serving,
and router registration.  Routers are small transport adapters; services own
business decisions and repositories own persistence.

* `catalog` manages products, ingredients, prices, promotions, and Thai/English
  keyword aliases.
* `conversations` records inbound and outbound messages, resolves product
  context, selects a safe canned response, and respects manual takeover.
* `orders` owns cart creation, total calculation, address capture, payment
  review, fulfillment status, and inventory reservation.
* `integrations` normalizes inbound webhook events and exposes outbound sender
  interfaces.  Facebook, TikTok, and Shopee adapters are disabled until their
  documented credential values are supplied through environment variables.
* `notifications` writes sales events to an outbox and uses the LINE Messaging
  API adapter only when it is configured.  Failures remain visible and
  retryable; no notification is silently represented as sent.

### Product-memory and conversation policy

Long-lived product facts and keyword aliases are stored in the database.
Per-customer context stores the active product, selected quantity, current
checkout stage, and takeover state with an expiry.  The local implementation
uses a durable session table; production can select Redis via configuration.

Automation uses deterministic intents (`greeting`, `product_lookup`,
`ingredients`, `price`, `delivery`, `buy`, `payment`, `address`, and
`fallback`) so it is testable without an AI key.  An optional model-provider
adapter may improve wording, but it cannot invent product facts, charge a
customer, or bypass manual-review rules.

### Admin PWA

The Thai-first dashboard has five views:

1. Overview: counts, conversion, latest orders, integration truth status.
2. Unified inbox: channel filters, message history, context, suggested reply,
   and a persisted human-takeover switch.
3. Product memory: CRUD for products, promotions, ingredients, and aliases.
4. Orders: draft through fulfilled/cancelled statuses, payment evidence state,
   and a manual review action.
5. Integrations: webhook URLs, required environment-variable names, and
   configuration status only.  It never displays or stores a secret in the
   browser.

The PWA includes a manifest, service worker, keyboard-accessible controls,
mobile breakpoints, and an offline shell.  Live data requests report a clear
retry state when offline.

## Data flow

1. A verified platform webhook is normalized to an inbound message.
2. The conversation service finds an explicit keyword match, otherwise uses the
   active session product, persists the message/context, and produces a reply.
3. If a staff member has taken over, the message is shown in the inbox but no
   automated outbound reply is sent.
4. A purchase request becomes a draft order.  The customer can select a
   supported payment method, submit payment evidence, and await human or an
   authorized verifier's review.
5. A confirmed order writes an outbox event.  LINE delivery is attempted only
   when the account is configured; the dashboard shows the result.

All webhook handlers use an event idempotency key, return appropriate 4xx
responses for malformed or invalidly signed events, and do not expose internal
errors to a sender.

## External integration contract

The project must not pretend to be connected to Meta, TikTok, Shopee, a
payment verifier, an LLM, or LINE.  Each adapter reports one of `unconfigured`,
`configured`, `verified`, `degraded`, or `disabled`.

* Credentials, webhook verification tokens, signing secrets, and provider API
  keys live in environment variables or the deployment secret manager—not in
  git, SQL seed data, frontend JavaScript, screenshots, or generated ZIPs.
* Platform-specific signature validation and outbound API calls are isolated
  behind adapters and have fixture-based tests.  Live verification is a
  deployment acceptance gate requiring the account owner.
* Payment slips begin as `pending_review`; a third-party verification result is
  an optional provider integration, never a fabricated approval.

## Error handling and safety

API responses use stable error codes and Thai-readable messages.  Validation
rejects negative quantities, unavailable products, invalid status transitions,
and missing recipient details.  Audit records capture automation decisions,
takeover changes, order status changes, and notification outcomes.  The app
uses conservative skincare wording from the source catalogue and does not
make medical or guaranteed-result claims.

## Seed knowledge base

The initial seed contains the four products in the execution brief:

* Loe Vit C Aura Serum, 200 ml: 98 THB, bundle 2 for 169 THB; its eight listed
  ingredients and product aliases.
* Loe Charcoal Mud Dtox & Whitening Soap, 100 g: 89 THB.
* Choe Foundation Cream sachet pack: 5 for 100 THB.
* The Copper Rouges Series Capsule Cream, 50 g: 390 THB.

Product copy is editable in the dashboard and source data is marked as
merchant-provided until independently verified.

## Verification strategy

Unit and API tests prove keyword/context recall, human override behavior,
checkout totals, invalid transitions, secret-free integration status, webhook
idempotency, and notification outbox behavior.  Browser smoke checks prove the
PWA starts, renders all five views, and calls the local API.  Static checks
ensure no placeholder tokens or claims of a verified connection appear in
seeded configuration.

## Deliverables

The repository will contain the runnable application, a PostgreSQL-compatible
schema, seed data, environment template, setup/deployment documentation,
automated tests, an honest release report, and a deterministic local packaging
script.  The package contains source and documentation, not copied secrets or
unverified TikTok product media.
