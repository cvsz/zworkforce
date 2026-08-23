# U.Perfect Social Commerce Autobot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a secure, locally runnable U.Perfect social-commerce admin PWA and FastAPI core with product memory, sales automation, orders, LINE notification outbox, and honest Facebook/TikTok/Shopee integration boundaries.

**Architecture:** A FastAPI API serves a vanilla JavaScript PWA and delegates domain work to focused services backed by SQLite in local/test mode. Repository and adapter contracts preserve a PostgreSQL/Redis production path, while outbound platforms remain truthfully unconfigured until account-owner secrets and verification are supplied.

**Tech Stack:** Python 3.14, FastAPI, Uvicorn, SQLite (`sqlite3`), Pytest, HTML/CSS/ES modules, Web App Manifest, Service Worker.

## Global Constraints

* Use the official brand spelling `U.Perfect` everywhere.
* Support Android, iOS, and Windows through an installable responsive PWA.
* Keep all API tokens, signing secrets, account identifiers, and webhook verification values out of source code, seed data, browser storage, generated package artifacts, and test output.
* Show a platform as connected only after a verified integration state is recorded; the local seed state is `unconfigured`.
* Treat payment proof as `pending_review` unless an authorized verification result or an administrator approves it.
* Preserve manual human takeover: an automated reply is never emitted for a taken-over conversation.
* Product descriptions are merchant-provided and must not claim medical outcomes or guaranteed results.
* Every state-changing HTTP route returns a stable JSON error code for invalid input or an invalid transition.
* Do not include TikTok CAPTCHA images or claim that product media was exported.
* This workspace has no Git repository; record verification in documentation instead of attempting commits.

---

## File structure

```text
app/
  __init__.py                    # package marker
  config.py                      # validated environment configuration
  database.py                    # SQLite connection, migration, transactions
  schemas.py                     # API DTOs and typed domain values
  seed.py                        # U.Perfect catalog and aliases
  repositories.py                # persistence operations and idempotency store
  services/
    catalog.py                   # product, keyword, ingredient operations
    conversations.py             # context resolution, safe reply, takeover
    orders.py                    # carts, pricing, payment and fulfilment states
    integrations.py              # configuration truth and inbound normalization
    notifications.py             # retryable LINE notification outbox
  api.py                         # JSON endpoint registration
  main.py                        # application factory and static serving
web/
  index.html                     # accessible dashboard shell
  styles.css                     # responsive lavender design system
  app.js                         # API client, routing, rendering, actions
  manifest.webmanifest           # install metadata
  service-worker.js              # offline shell cache
database_schema.sql              # PostgreSQL deployment schema
requirements.txt                 # runtime dependencies
requirements-dev.txt             # test dependencies
.env.example                     # secret names only
README.md                        # setup, operation, and external gates
u_perfect_final_release_report.md # factual deliverable and verification report
scripts/package_release.py       # deterministic secret-free ZIP packaging
tests/
  conftest.py                    # isolated app and database fixtures
  test_catalog.py
  test_conversations.py
  test_orders.py
  test_integrations.py
  test_api.py
  test_packaging.py
```

## Task 1: Create the runnable application shell and configuration boundary

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `app/main.py`
- Create: `tests/conftest.py`
- Create: `tests/test_api.py`

**Interfaces:**
- Produces `Settings.from_environment() -> Settings`, `Database(path: str)`, and `create_app(settings: Settings | None = None) -> FastAPI`.
- Later tasks consume `app.state.db` and the `client` fixture.

- [ ] **Step 1: Write the failing settings and health tests**

```python
def test_settings_do_not_expose_secret_values(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "not-for-output")
    settings = Settings.from_environment()
    assert settings.integration_status("line") == "configured"
    assert "not-for-output" not in repr(settings)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "brand": "U.Perfect"}
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `pytest tests/test_api.py -q`

Expected: import failure because the application package does not yet exist.

- [ ] **Step 3: Implement minimal runtime configuration and application factory**

```python
@dataclass(frozen=True, repr=False)
class Settings:
    database_path: str
    line_channel_access_token: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            database_path=os.getenv("UPERFECT_DATABASE_PATH", "uperfect.db"),
            line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
        )

    def integration_status(self, name: str) -> str:
        return "configured" if name == "line" and self.line_channel_access_token else "unconfigured"


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="U.Perfect Social Commerce OS")
    app.state.settings = settings or Settings.from_environment()
    app.get("/api/health")(lambda: {"status": "ok", "brand": "U.Perfect"})
    return app
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `pytest tests/test_api.py -q`

Expected: both tests pass and output contains no configured secret value.

- [ ] **Step 5: Add a database migration transaction and isolated test fixture**

```python
@contextmanager
def transaction(self) -> Iterator[sqlite3.Connection]:
    connection = self.connect()
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
```

- [ ] **Step 6: Run the application-shell test set**

Run: `pytest tests/test_api.py -q`

Expected: PASS.

## Task 2: Implement the product catalogue, keyword memory, and PostgreSQL schema

**Files:**
- Create: `app/schemas.py`
- Create: `app/seed.py`
- Create: `app/repositories.py`
- Create: `app/services/catalog.py`
- Create: `database_schema.sql`
- Create: `tests/test_catalog.py`
- Modify: `app/database.py`

**Interfaces:**
- Consumes `Database.transaction()`.
- Produces `CatalogService.find_by_text(text: str) -> Product | None`, `CatalogService.get(product_id: str) -> Product`, and `CatalogService.list_products() -> list[Product]`.
- `Product` has `id`, `name`, `size`, `price_thb`, `aliases`, `ingredients`, and `merchant_provided` fields.

- [ ] **Step 1: Write failing catalogue and alias-recall tests**

```python
def test_keyword_match_returns_the_seeded_serum(catalog):
    product = catalog.find_by_text("สนใจวิตซีโลเอ้ มีส่วนผสมอะไร")
    assert product is not None
    assert product.id == "LOE_VITC_SERUM"
    assert product.price_thb == Decimal("98.00")
    assert len(product.ingredients) == 8


def test_unknown_keyword_does_not_invent_a_product(catalog):
    assert catalog.find_by_text("ครีมที่ไม่มีในร้าน") is None
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `pytest tests/test_catalog.py -q`

Expected: failure because `CatalogService` and seeded schema are absent.

- [ ] **Step 3: Create relational tables and seed merchant-provided product facts**

```sql
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  size TEXT NOT NULL,
  price_thb NUMERIC NOT NULL CHECK (price_thb >= 0),
  merchant_provided INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS product_keywords (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  keyword TEXT NOT NULL COLLATE NOCASE,
  UNIQUE(product_id, keyword)
);
CREATE TABLE IF NOT EXISTS ingredients (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  benefit_copy TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY(product_id, name)
);
```

- [ ] **Step 4: Implement deterministic alias matching**

```python
def find_by_text(self, text: str) -> Product | None:
    normalized = " ".join(text.casefold().split())
    matches = self.repository.find_keyword_matches(normalized)
    return max(matches, key=lambda product: len(product.matched_alias), default=None)
```

- [ ] **Step 5: Run catalogue tests to verify they pass**

Run: `pytest tests/test_catalog.py -q`

Expected: PASS for known aliases and unknown queries.

- [ ] **Step 6: Check PostgreSQL deployment schema is aligned with local tables**

Run: `rg -n "CREATE TABLE (products|product_keywords|ingredients)" database_schema.sql`

Expected: one definition for each of the three catalogue entities.

## Task 3: Implement conversation memory, safe automation, and manual takeover

**Files:**
- Create: `app/services/conversations.py`
- Create: `tests/test_conversations.py`
- Modify: `app/database.py`
- Modify: `app/repositories.py`
- Modify: `app/schemas.py`

**Interfaces:**
- Consumes `CatalogService.find_by_text()` and `Clock.now() -> datetime`.
- Produces `ConversationService.receive(event: InboundMessage) -> AutomationResult`, `ConversationService.set_takeover(conversation_id: str, enabled: bool) -> Conversation`, and `ConversationService.get_context(conversation_id: str) -> ConversationContext`.
- `AutomationResult` contains `conversation`, `reply: str | None`, `intent`, `automated`, and `active_product_id`.

- [ ] **Step 1: Write failing context, pricing, and takeover tests**

```python
def test_product_context_is_reused_for_an_ingredient_question(conversations):
    conversations.receive(InboundMessage("facebook", "a1", "สนใจวิตซีโลเอ้"))
    result = conversations.receive(InboundMessage("facebook", "a1", "มีส่วนผสมอะไรบ้าง"))
    assert result.active_product_id == "LOE_VITC_SERUM"
    assert result.intent == "ingredients"
    assert "Niacinamide" in result.reply


def test_takeover_suppresses_automatic_reply(conversations):
    first = conversations.receive(InboundMessage("shopee", "a2", "สนใจสบู่"))
    conversations.set_takeover(first.conversation.id, True)
    result = conversations.receive(InboundMessage("shopee", "a2", "ราคาเท่าไร"))
    assert result.automated is False
    assert result.reply is None
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `pytest tests/test_conversations.py -q`

Expected: failure because sessions, messages, and automation decisions are absent.

- [ ] **Step 3: Add conversation/session/message tables and a bounded state machine**

```python
INTENTS = ("greeting", "product_lookup", "ingredients", "price", "delivery", "buy", "payment", "address", "fallback")

def resolve_intent(text: str) -> str:
    value = text.casefold()
    if any(term in value for term in ("ส่วนผสม", "สารสกัด")):
        return "ingredients"
    if any(term in value for term in ("ราคา", "กี่บาท", "โปร")):
        return "price"
    return "fallback"
```

- [ ] **Step 4: Persist context with expiry and apply manual-takeover policy**

```python
if conversation.human_takeover:
    self.repository.append_message(conversation.id, "inbound", event.text)
    return AutomationResult(conversation, None, "fallback", False, conversation.active_product_id)

context = self.repository.get_live_context(conversation.id, now=self.clock.now())
product = self.catalog.find_by_text(event.text) or self.catalog.get_optional(context.active_product_id)
```

- [ ] **Step 5: Run conversation tests to verify they pass**

Run: `pytest tests/test_conversations.py -q`

Expected: PASS; takeover prevents an outgoing message from being recorded.

- [ ] **Step 6: Verify the reply data is merchant-fact bound**

Run: `pytest tests/test_conversations.py -q -k "ingredient or price"`

Expected: PASS with no model-provider configuration needed.

## Task 4: Implement orders, promotions, payment review, and inventory reservation

**Files:**
- Create: `app/services/orders.py`
- Create: `tests/test_orders.py`
- Modify: `app/database.py`
- Modify: `app/repositories.py`
- Modify: `app/schemas.py`
- Modify: `app/seed.py`

**Interfaces:**
- Consumes `CatalogService.get(product_id: str) -> Product`.
- Produces `OrderService.create_draft(...) -> Order`, `OrderService.submit_payment_evidence(order_id: str, reference: str) -> Order`, and `OrderService.transition(order_id: str, target: OrderStatus, actor: str) -> Order`.
- Valid status transitions are `draft -> awaiting_payment -> pending_review -> confirmed -> fulfilled`; `draft`, `awaiting_payment`, and `pending_review` may transition to `cancelled`.

- [ ] **Step 1: Write failing total and transition-guard tests**

```python
def test_serum_bundle_uses_merchant_promotion(orders):
    order = orders.create_draft(product_id="LOE_VITC_SERUM", quantity=2, customer_name="Mali")
    assert order.total_thb == Decimal("169.00")
    assert order.status == "awaiting_payment"


def test_payment_evidence_requires_review_before_confirmation(orders):
    order = orders.create_draft(product_id="LOE_SOAP", quantity=1, customer_name="Mali")
    reviewed = orders.submit_payment_evidence(order.id, "slip-reference")
    assert reviewed.status == "pending_review"
    with pytest.raises(InvalidTransition):
        orders.transition(order.id, "fulfilled", actor="admin")
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `pytest tests/test_orders.py -q`

Expected: failure because orders and transitions are absent.

- [ ] **Step 3: Add persistent order, item, inventory, and audit tables**

```sql
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  customer_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft','awaiting_payment','pending_review','confirmed','fulfilled','cancelled')),
  total_thb NUMERIC NOT NULL CHECK (total_thb >= 0),
  payment_reference TEXT,
  created_at TEXT NOT NULL
);
```

- [ ] **Step 4: Implement promotion calculation and explicit transition validation**

```python
def transition(self, order_id: str, target: OrderStatus, actor: str) -> Order:
    order = self.repository.get_order(order_id)
    if target not in ALLOWED_TRANSITIONS[order.status]:
        raise InvalidTransition(order.status, target)
    return self.repository.update_order_status(order.id, target, actor)
```

- [ ] **Step 5: Run order tests to verify they pass**

Run: `pytest tests/test_orders.py -q`

Expected: PASS; no path can move a payment directly to fulfilled.

- [ ] **Step 6: Confirm all restricted payment statuses appear in the schema**

Run: `rg -n "pending_review|confirmed|fulfilled" app database_schema.sql`

Expected: status strings appear in persistence and transition code.

## Task 5: Implement truthful integration state, idempotent webhook intake, and LINE outbox

**Files:**
- Create: `app/services/integrations.py`
- Create: `app/services/notifications.py`
- Create: `tests/test_integrations.py`
- Modify: `app/config.py`
- Modify: `app/database.py`
- Modify: `app/repositories.py`
- Modify: `app/schemas.py`

**Interfaces:**
- Consumes `Settings.integration_status(name: str) -> str` and `ConversationService.receive(event: InboundMessage) -> AutomationResult`.
- Produces `IntegrationService.statuses() -> list[IntegrationStatus]`, `IntegrationService.accept(event: WebhookEvent) -> WebhookReceipt`, and `NotificationService.deliver_pending(sender: NotificationSender) -> DeliverySummary`.
- `WebhookReceipt` has `accepted`, `duplicate`, and `message_id` fields. `NotificationSender.send(destination: str, body: str) -> None` is injectable for tests.

- [ ] **Step 1: Write failing truth-status, deduplication, and outbox tests**

```python
def test_seeded_platforms_are_not_presented_as_verified(integrations):
    assert {item.status for item in integrations.statuses()} == {"unconfigured"}


def test_same_verified_event_is_processed_once(integrations, signed_event):
    first = integrations.accept(signed_event)
    second = integrations.accept(signed_event)
    assert first.accepted is True
    assert second.duplicate is True


def test_line_failure_stays_retryable(notifications, failing_sender):
    summary = notifications.deliver_pending(failing_sender)
    assert summary.failed == 1
    assert notifications.pending_count() == 1
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `pytest tests/test_integrations.py -q`

Expected: failure because integrations and notification outbox are absent.

- [ ] **Step 3: Persist integration truth, idempotency keys, and notification events**

```sql
CREATE TABLE IF NOT EXISTS webhook_receipts (
  provider TEXT NOT NULL,
  event_id TEXT NOT NULL,
  received_at TEXT NOT NULL,
  PRIMARY KEY(provider, event_id)
);
CREATE TABLE IF NOT EXISTS notification_outbox (
  id TEXT PRIMARY KEY,
  destination TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','sent','failed')),
  attempts INTEGER NOT NULL DEFAULT 0
);
```

- [ ] **Step 4: Implement provider validation without hard-coded credentials**

```python
def accept(self, event: WebhookEvent) -> WebhookReceipt:
    adapter = self.adapters[event.provider]
    adapter.validate(event, self.settings)
    if not self.repository.claim_webhook(event.provider, event.event_id):
        return WebhookReceipt(accepted=True, duplicate=True, message_id=None)
    result = self.conversations.receive(adapter.normalize(event))
    return WebhookReceipt(accepted=True, duplicate=False, message_id=result.conversation.id)
```

- [ ] **Step 5: Implement retryable notification delivery with failure visibility**

```python
for event in self.repository.pending_notifications(limit=20):
    try:
        sender.send(event.destination, event.body)
    except Exception:
        self.repository.record_notification_failure(event.id)
        failed += 1
    else:
        self.repository.mark_notification_sent(event.id)
        sent += 1
```

- [ ] **Step 6: Run integration tests to verify they pass**

Run: `pytest tests/test_integrations.py -q`

Expected: PASS; an unconfigured or duplicate platform event cannot create two replies.

## Task 6: Expose API routes and ensure input errors are stable and secret-free

**Files:**
- Create: `app/api.py`
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes all services from Tasks 2–5.
- Produces JSON routes: `GET /api/health`, `GET|POST /api/products`, `GET /api/conversations`, `POST /api/conversations/{id}/takeover`, `POST /api/messages`, `GET|POST /api/orders`, `POST /api/orders/{id}/payment-evidence`, `POST /api/orders/{id}/transition`, `GET /api/integrations`, and `POST /api/webhooks/{provider}`.
- Failure envelope is `{"error": {"code": str, "message": str}}`.

- [ ] **Step 1: Write failing endpoint contract tests**

```python
def test_products_and_integrations_are_listed_without_secrets(client):
    products = client.get("/api/products")
    integrations = client.get("/api/integrations")
    assert products.status_code == 200
    assert integrations.json()["items"][0]["status"] == "unconfigured"
    assert "token" not in integrations.text.casefold()


def test_invalid_order_transition_has_stable_error(client):
    response = client.post("/api/orders/missing/transition", json={"target": "fulfilled"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `pytest tests/test_api.py -q`

Expected: endpoint-not-found or assertion failures for the unimplemented contract.

- [ ] **Step 3: Register typed routes and exception handlers**

```python
@router.exception_handler(DomainError)
async def domain_error(_: Request, error: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=error.http_status,
        content={"error": {"code": error.code, "message": error.public_message}},
    )
```

- [ ] **Step 4: Make webhook authorization failures explicit**

```python
@router.post("/api/webhooks/{provider}")
def accept_webhook(provider: str, payload: dict[str, Any], request: Request) -> WebhookReceipt:
    event = WebhookEvent.from_request(provider, payload, request.headers)
    return integration_service.accept(event)
```

- [ ] **Step 5: Run API tests to verify they pass**

Run: `pytest tests/test_api.py -q`

Expected: PASS; error envelopes contain a code and never echo a secret.

## Task 7: Build the accessible responsive PWA dashboard

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`
- Create: `web/manifest.webmanifest`
- Create: `web/service-worker.js`
- Modify: `app/main.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes the Task 6 API route contract.
- Produces `window.UperfectApp.loadDashboard()`, `window.UperfectApp.setTakeover(id, enabled)`, and `window.UperfectApp.submitMessage(payload)`.
- Static root `/` serves `web/index.html`; `/manifest.webmanifest` and `/service-worker.js` are served with their respective content types.

- [ ] **Step 1: Write failing static-app contract tests**

```python
def test_dashboard_shell_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "U.Perfect Social Commerce OS" in response.text
    assert 'rel="manifest"' in response.text


def test_pwa_manifest_declares_cross_platform_installability(client):
    manifest = client.get("/manifest.webmanifest").json()
    assert manifest["display"] == "standalone"
    assert manifest["name"].startswith("U.Perfect")
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `pytest tests/test_api.py -q -k "dashboard or manifest"`

Expected: 404 responses because no static client has been created.

- [ ] **Step 3: Build semantic dashboard markup and compact responsive styles**

```html
<main id="app" aria-live="polite">
  <header class="topbar"><h1>U.Perfect Social Commerce OS</h1></header>
  <nav aria-label="ส่วนงาน"><button data-view="overview">ภาพรวม</button></nav>
  <section id="view" tabindex="-1"></section>
</main>
```

```css
@media (max-width: 720px) {
  .dashboard-grid { grid-template-columns: 1fr; }
  .sidebar { position: static; }
  button, input, select { min-height: 44px; }
}
```

- [ ] **Step 4: Implement API-driven views and safe integration rendering**

```javascript
async function loadIntegrations() {
  const { items } = await api('/api/integrations');
  return items.map(({ provider, status, webhook_path }) =>
    `<article><h3>${escapeHtml(provider)}</h3><p>${escapeHtml(status)}</p><code>${escapeHtml(webhook_path)}</code></article>`
  ).join('');
}
```

- [ ] **Step 5: Add manifest and offline shell without caching API mutations**

```javascript
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request)));
});
```

- [ ] **Step 6: Run PWA endpoint tests to verify they pass**

Run: `pytest tests/test_api.py -q -k "dashboard or manifest"`

Expected: PASS.

## Task 8: Add production schema, operational documentation, and deterministic packaging

**Files:**
- Create: `scripts/package_release.py`
- Create: `u_perfect_final_release_report.md`
- Modify: `README.md`
- Modify: `database_schema.sql`
- Modify: `.env.example`
- Create: `tests/test_packaging.py`

**Interfaces:**
- Consumes the repository layout from Tasks 1–7.
- Produces `python3 scripts/package_release.py --output /tmp/uperfect-release.zip` and a ZIP containing source/docs only.
- The release report distinguishes locally verified functionality from account-owner deployment gates.

- [ ] **Step 1: Write failing packaging and secret-exclusion tests**

```python
def test_release_package_contains_core_artifacts_but_no_env_file(tmp_path):
    output = tmp_path / "release.zip"
    build_release_archive(output)
    with ZipFile(output) as archive:
        names = set(archive.namelist())
    assert {"README.md", "database_schema.sql", "web/index.html"} <= names
    assert ".env" not in names
    assert not any(name.endswith(".db") for name in names)
```

- [ ] **Step 2: Run targeted test to verify it fails**

Run: `pytest tests/test_packaging.py -q`

Expected: import failure because the packager is absent.

- [ ] **Step 3: Implement a fixed allow-list archive builder**

```python
ALLOWED_PATHS = ("app", "web", "tests", "docs", "scripts", "README.md", "database_schema.sql", "requirements.txt", "requirements-dev.txt", ".env.example", "u_perfect_final_release_report.md")

def build_release_archive(output: Path) -> None:
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in iter_allowed_files(ALLOWED_PATHS):
            archive.write(path, path.as_posix())
```

- [ ] **Step 4: Document every external account-owner gate honestly**

```markdown
## Deployment gates

Facebook Messenger, TikTok Shop, Shopee, LINE Messaging API, a payment verifier,
and an optional LLM each require account-owner credentials and official webhook
verification. The local test suite does not represent any of them as live.
```

- [ ] **Step 5: Run packaging tests to verify they pass**

Run: `pytest tests/test_packaging.py -q`

Expected: PASS; package contents contain no `.env` or database file.

- [ ] **Step 6: Build and inspect a release archive**

Run: `python3 scripts/package_release.py --output /tmp/uperfect-release.zip && unzip -l /tmp/uperfect-release.zip`

Expected: archive lists code, web client, schema, tests, docs, and no credential file.

## Task 9: Run full verification and complete the factual release audit

**Files:**
- Modify: `u_perfect_final_release_report.md`
- Modify: `README.md`

**Interfaces:**
- Consumes every runtime and verification artifact from Tasks 1–8.
- Produces a reproducible local verification command list and a release report whose status labels match actual evidence.

- [ ] **Step 1: Run all automated tests**

Run: `pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run syntax and secret scans**

Run: `python3 -m compileall -q app scripts && rg -n -i 'sample[_-]?credential|sample[_-]?token|access[_-]?token\s*=\s*["'"'][^"'"']+' --glob '!rewrite-uperfect.md' .`

Expected: compile succeeds; secret scan finds no value-bearing credential literals outside the source export.

- [ ] **Step 3: Start the server and perform a local HTTP smoke check**

Run: `uvicorn app.main:app --host 127.0.0.1 --port 8765`

In a second terminal run: `curl -fsS http://127.0.0.1:8765/api/health && curl -fsS http://127.0.0.1:8765/ | rg -o 'U\.Perfect Social Commerce OS'`

Expected: health JSON reports `ok`; dashboard title is present.

- [ ] **Step 4: Update the release report with observed evidence**

```markdown
| Capability | Evidence | Status |
| --- | --- | --- |
| Local product-memory workflow | `pytest tests/test_conversations.py -q` | Verified locally |
| Cross-platform installable client | manifest and responsive smoke check | Verified locally |
| Facebook/TikTok/Shopee live delivery | account owner authorization and webhook verification | Deployment gate |
```

- [ ] **Step 5: Rebuild the ZIP after final report updates**

Run: `python3 scripts/package_release.py --output /tmp/uperfect-release.zip && pytest tests/test_packaging.py -q`

Expected: release archive and packaging test pass.

## Plan self-review

| Design requirement | Plan coverage |
| --- | --- |
| Cross-platform admin client | Task 7 PWA and manifest |
| Product catalogue and eight serum ingredients | Task 2 seed/schema/tests |
| Context memory and safe automated answers | Task 3 |
| Closing, payment review, order tracking | Task 4 |
| Facebook, TikTok, Shopee and LINE boundaries | Task 5 and Task 6 |
| Secret safety and truthful connection status | Tasks 1, 5, 6, 8, 9 |
| PostgreSQL/Redis deployment path | Tasks 2, 3, and 8 documentation/schema |
| Testable release package and factual report | Tasks 8 and 9 |

The plan deliberately does not fabricate an external account connection, payment verification result, native binary, or exported TikTok media. Those are truthfully represented as account-owner deployment acceptance gates.
