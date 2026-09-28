# P0/P1 Fix — GitHub Webhook Delivery 404

**Status:** Open — P0 operational integration failure, P1 hardening work  
**Scope:** `cvsz/zworkforce` GitHub webhook ingress and processing  
**Observed:** 2026-09-28  
**Primary host:** `https://zwf.zeaz.dev`

## Executive summary

GitHub is successfully delivering webhook requests to `https://zwf.zeaz.dev/github/webhook`, but the ingress forwards those requests to `http://127.0.0.1:9570/github/webhook`, where the upstream returns `404 Not Found`.

The repository source currently exposes the GitHub webhook handler at:

```text
POST /webhooks/github
```

in `services/zc-api/app.py`, not at `/github/webhook`. This establishes a concrete route-contract mismatch between the observed production ingress path and the application route.

**P0 objective:** restore a working GitHub webhook path without weakening signature verification or event-processing guarantees.

**P1 objective:** make the webhook contract explicit, observable, idempotent, tested, and deployment-safe so a future ingress/application path mismatch cannot silently recur.

---

## 1. Verified production evidence

The supplied edge/ingress log contains repeated GitHub webhook requests to:

```text
POST https://zwf.zeaz.dev/github/webhook
```

with upstream:

```text
originService: http://127.0.0.1:9570
```

and repeated:

```text
404 Not Found
```

The affected GitHub events include at least:

- `workflow_run`
- `workflow_job`
- `check_run`
- `check_suite`
- `issue_comment`

GitHub also supplies `X-GitHub-Delivery` and `X-Hub-Signature-256` headers in the observed requests, so delivery is reaching the HTTP origin with the expected webhook metadata.

**Conclusion:** the evidence does not indicate a GitHub delivery outage. The immediate failure is the origin route contract.

---

## 2. Verified repository state

The current `services/zc-api/app.py` implementation defines:

```python
@app.post("/webhooks/github")
async def github_webhook(request: Request):
```

and performs signature verification using the raw request body and `X-Hub-Signature-256` before processing the event.

The repository also contains dedicated GitHub webhook tests at:

```text
services/zc-api/tests/test_github_webhook.py
```

This means the application already has a webhook implementation and test surface; the first P0 fix should therefore reconcile the deployed ingress contract with the existing application contract rather than creating a second independent webhook implementation.

---

## 3. P0 — Restore the production route contract

### Required decision

Choose one canonical public webhook path and make every layer agree on it.

Preferred canonical application route:

```text
POST /webhooks/github
```

Two safe implementation strategies exist:

### Option A — Preferred: ingress rewrite

Keep the public GitHub webhook URL unchanged if GitHub is already configured with:

```text
https://zwf.zeaz.dev/github/webhook
```

and rewrite:

```text
/github/webhook -> /webhooks/github
```

before the request reaches `127.0.0.1:9570`.

Advantages:

- no application API compatibility change;
- no duplicate webhook handler;
- preserves the existing GitHub webhook URL;
- smallest blast radius.

### Option B — Application compatibility route

Expose `/github/webhook` as a compatibility route that delegates to the existing `/webhooks/github` handler.

If this option is selected, both paths must share exactly the same signature verification, parsing, persistence, idempotency, and event dispatch implementation. Do not duplicate business logic.

### P0 acceptance criteria

- `POST /github/webhook` no longer returns `404`.
- A valid GitHub webhook reaches the existing handler.
- Invalid `X-Hub-Signature-256` remains rejected.
- Existing `/webhooks/github` behavior remains compatible.
- GitHub delivery IDs are preserved end-to-end.
- No webhook secret is written to logs.
- A real/replayed GitHub delivery can be correlated through logs/metrics without logging sensitive payload data.
- Production ingress and application route configuration are tested together.

---

## 4. P1 — Webhook reliability and security hardening

### 4.1 Signature verification

Keep HMAC verification based on the raw request body and `X-Hub-Signature-256`.

Requirements:

- reject missing signature;
- reject malformed signature;
- use constant-time comparison;
- never log the webhook secret;
- never log the complete signed payload in normal production logs.

### 4.2 Idempotency

Use `X-GitHub-Delivery` as the webhook delivery identifier.

Requirements:

- persist/track delivery IDs before irreversible processing;
- duplicate delivery must not execute side effects twice;
- retries must be safe;
- idempotency state must have a bounded retention policy appropriate for GitHub retries/replays.

### 4.3 Event validation

Explicitly handle supported GitHub event types and define behavior for unsupported events.

At minimum:

```text
workflow_run
workflow_job
check_run
check_suite
issue_comment
```

Unsupported events should be acknowledged safely when appropriate rather than causing an uncontrolled retry storm.

### 4.4 Fast acknowledgement

The HTTP webhook handler should acknowledge delivery quickly and move expensive work to the existing queue/background-processing mechanism where possible.

Do not make GitHub wait for long-running AI, CI, repository, or deployment operations.

### 4.5 Observability

Add/verify metrics for:

- webhook requests received;
- accepted deliveries;
- rejected signatures;
- duplicate deliveries;
- unsupported events;
- processing failures;
- processing latency;
- queue enqueue failures.

Logs should include safe correlation identifiers such as:

```text
X-GitHub-Delivery
X-GitHub-Event
repository/full_name
installation_id (when available)
```

but must exclude secrets and unnecessary request-body content.

### 4.6 Configuration contract

The production deployment must have one documented source of truth for:

```text
public webhook URL
public-to-origin rewrite
origin port
application route
webhook secret configuration
supported events
```

A deployment check should fail before release if the configured public route and application route are inconsistent.

---

## 5. Test matrix

### Unit tests

- valid signature → accepted;
- missing signature → rejected;
- invalid signature → rejected;
- malformed signature → rejected;
- known event → parsed;
- unknown event → safe handling;
- duplicate delivery ID → idempotent;
- distinct delivery IDs → independently processed.

### Integration tests

Verify the exact production contract:

```text
POST /github/webhook
        ↓
proxy/ingress rewrite
        ↓
POST /webhooks/github
        ↓
application
```

Also verify the direct application endpoint:

```text
POST /webhooks/github
```

### Regression test

The specific failure must become a permanent regression test:

```text
POST /github/webhook must not return 404
```

### Deployment smoke test

After deployment:

```bash
curl -i -X POST https://zwf.zeaz.dev/github/webhook \
  -H 'Content-Type: application/json' \
  -d '{}'
```

This synthetic request is expected to be rejected by signature validation, not by route resolution. Therefore a healthy route should produce an authentication/signature error such as `401`, rather than `404`.

A signed fixture should then prove the complete acceptance path.

---

## 6. Deployment validation

Before declaring the P0 closed:

- [ ] inspect the live listener on port `9570`;
- [ ] inspect the active ingress/reverse-proxy configuration;
- [ ] verify the public `/github/webhook` mapping;
- [ ] verify `/webhooks/github` on the origin;
- [ ] apply the smallest safe route-contract fix;
- [ ] run webhook unit tests;
- [ ] run API/integration tests;
- [ ] run lint/type checks required by the repository;
- [ ] deploy to the intended environment;
- [ ] replay a signed GitHub fixture;
- [ ] confirm HTTP `2xx` for a valid delivery;
- [ ] confirm invalid signatures remain rejected;
- [ ] confirm duplicate delivery is idempotent;
- [ ] inspect logs and metrics for the delivery ID;
- [ ] confirm no new `404 /github/webhook` events;
- [ ] record exact deployment commit SHA and validation evidence.

Do not claim production success without the corresponding runtime evidence.

---

## 7. Rollback

The preferred rollback is to restore the previous ingress/application route configuration without changing webhook secrets or deleting GitHub webhook configuration.

If the fix is implemented as an ingress rewrite, rollback is isolated to the ingress rule.

If the fix is implemented as an application compatibility route, rollback is the application deployment revision.

Do not rotate the GitHub webhook secret as part of this route fix unless separate evidence proves the secret is compromised or incorrect.

---

## 8. Definition of Done

### P0

- [ ] `/github/webhook` resolves through production ingress.
- [ ] Existing `/webhooks/github` handler receives the request.
- [ ] Valid signed GitHub delivery returns a successful response.
- [ ] Signature verification remains enforced.
- [ ] No production `404` remains for the configured GitHub webhook URL.

### P1

- [ ] Delivery-id idempotency is verified.
- [ ] Event handling is explicitly covered by tests.
- [ ] Webhook metrics and safe structured logging are available.
- [ ] Route configuration is documented and deployment-validated.
- [ ] Integration/smoke tests cover public ingress → application route.
- [ ] Runtime evidence is captured in the production evidence record.

---

## 9. Non-goals

This fix does **not** authorize unrelated refactors, provider changes, GitHub App permission changes, webhook secret rotation, or broad infrastructure migration.

Keep the P0 change narrowly scoped to restoring the webhook route contract and proving it end-to-end. Perform P1 hardening only where it directly improves the reliability/security of this webhook path.

---

## Source evidence

- Production ingress log supplied for the incident: repeated `POST /github/webhook` requests to `127.0.0.1:9570` returning `404 Not Found`.
- `services/zc-api/app.py`: current application route is `POST /webhooks/github` with `X-Hub-Signature-256` verification.
- `services/zc-api/tests/test_github_webhook.py`: existing webhook regression/unit-test surface.
