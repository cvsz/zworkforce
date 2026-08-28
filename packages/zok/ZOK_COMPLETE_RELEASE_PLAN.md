# Zok Complete Release Plan - Meta-Hardened Execution Ledger

**Document status:** Executable release ledger
**Assessment date:** 2026-08-10
**Release decision:** REWORK. This repository is a hardened developer/sandbox release, not a Gold Master.
**Canonical runtime:** Vite static client plus Express API adapter
**Primary deployment shape:** Caddy serves `dist/`; Caddy proxies `/api/*` to `127.0.0.1:3005`

## 1. Intent and Scope Discipline

The requested end state is an enterprise conversational-commerce operating system with measurable security, reliability, governance, AI controls, integrations, migration, education, and release evidence.

The simpler architecture that is valid for the current codebase is a single Vite/React client and a small Express adapter. The repository does not yet contain the external channel contracts, durable multi-tenant data layer, queue workers, identity provider, or observability needed for the full enterprise scope. The release process therefore separates:

1. Controls implemented and tested in this repository.
2. UI simulations that are useful for product discovery but are not integrations.
3. External or production gates that cannot be claimed without infrastructure evidence.

No UI card, static metric, mock delay, or documentation statement counts as a completed backend feature.

## 2. Current Architecture and Real Code Paths

```text
Browser
  -> Vite client (`src/main.jsx` -> `src/App.jsx`)
  -> `src/lib/api.js` adds same-origin credentials and CSRF header
  -> Express (`server.js`, 127.0.0.1:3005)
  -> session/auth middleware
  -> route validation
  -> serialized atomic JSON adapter (`server/db.json`)
```

The dashboard request path is:

1. `src/views/Dashboard/*` calls `apiFetch` for API-backed views.
2. `apiFetch` sends the `zok_session` cookie and reads the `zok_csrf` cookie for mutations.
3. `server.js` applies headers, CORS, body limit, rate limit, authentication, and CSRF checks before route handlers.
4. Mutation handlers use `updateDB`, which serializes read-modify-write operations and atomically renames a temporary file.
5. `test/server.test.js` exercises the path over HTTP rather than calling route functions directly.

The old `src/app/` Next route tree and generated `pages/*.html` artifacts are not imported by the Vite client and are not part of the canonical build. They must not be presented as shipped routes until they have a dedicated entrypoint and tests.

## 3. Execution Completed in This Hardening Pass

| Area | Change | Evidence | Status |
| --- | --- | --- | --- |
| Authentication | Removed hardcoded demo credentials from `src/views/Landing/Login.jsx`; added PBKDF2 admin login and HttpOnly session | `POST /api/auth/login`, `GET /api/auth/me`, logout test | Implemented |
| CSRF and origin | SameSite cookies, CSRF token/header validation, CORS origin allowlist | Mutation without token returns 403; valid mutation succeeds | Implemented |
| API abuse controls | 64KB JSON limit, per-IP route limits, strict input validation, safe errors | `test/server.test.js` and route checks | Implemented |
| Security headers | nosniff, frame denial, referrer policy, permissions policy, production HSTS | Health response assertions | Implemented |
| Storage integrity | Corrupt JSON is rejected; writes are serialized and atomic | `readDB`, `updateDB`, persisted mutation test | Implemented |
| Health | Public `/api/health` with DB-read check and no credential disclosure | HTTP smoke test | Implemented |
| Client session use | Dashboard API calls use `src/lib/api.js`; logout and 401 handling added | Vite build plus authenticated API path | Implemented |
| Integration honesty | Sandbox provider records start disconnected; toggle rejects unverified integrations with `409` | Request-path test for `/api/integrations/:id/toggle` | Implemented |
| Repository hygiene | Fixed malformed `.gitignore`; ignore `.env`, runtime DB, temp writes, dependencies, and build output | `.gitignore` source inspection; Git tracked-file audit remains external because this directory has no `.git` metadata | Implemented locally / Git audit pending |
| Runtime reduction | Vite is the canonical build/start path; unused Next runtime dependency removed | `package.json`, `npm audit --omit=dev` | Implemented |
| Documentation | README and deployment guide now distinguish real controls from simulations | This document and linked docs | Implemented |

## 4. Original Feature Scope Audit

### Pillar 1 - Infrastructure and Scalability

| Requirement | Actual state | Required evidence before release |
| --- | --- | --- |
| Developer Portal, API docs, rate limits, sandbox | `DeveloperPortal.jsx` is a UI simulation; API rate limiting is now local and in-memory | Versioned OpenAPI contract, authenticated sandbox, contract tests, documented quotas |
| System health, real-time status, latency, 99.99% SLA | `/api/health` exists; no metrics backend or SLA measurement | Metrics/alerts, latency percentile report, uptime data, signed SLO definition |
| One-click CSV/Excel migration | No migration endpoint or worker exists | Schema mapping, bounded streaming import, idempotency, dry-run report, rollback test |

**Pillar status:** PARTIAL. Local API controls exist; enterprise scalability does not.

### Pillar 2 - Advanced AI Intelligence

| Requirement | Actual state | Required evidence before release |
| --- | --- | --- |
| Thai dialect/context engine | UI selectors and local copy only; no model or evaluation harness | Prompt/model versioning, Thai dialect test set, quality thresholds, abuse tests |
| Hallucination guardrails and human-in-the-loop | `AIIntelligence.jsx` contains demo controls; no server enforcement or approval state | Server-side policy decision, blocked-response tests, approval/audit records |
| Token cost simulator | Local calculation UI only | Provider pricing source, deterministic calculator tests, budget enforcement |
| LINE/SMS smart escalation | No provider adapter, queue, retry policy, or delivery receipt | Signed provider webhooks, queue retry/dead-letter tests, consent and opt-out handling |

**Pillar status:** UI PARTIAL; runtime AI controls MISSING.

### Pillar 3 - Enterprise Governance

| Requirement | Actual state | Required evidence before release |
| --- | --- | --- |
| Field/channel-level RBAC | Every configured session is effectively `owner`; no policy evaluator | Tenant-aware principals, deny-by-default policy tests, field redaction tests |
| Agency hub and white-label | `EnterpriseGovernance.jsx` is static local data | Tenant isolation tests, scoped branding/config API, export/delete controls |
| Audit logs | Static demo rows; mutations do not emit durable audit events | Append-only audit store, actor/request IDs, retention and tamper evidence |

**Pillar status:** MISSING beyond the single-owner sandbox.

### Pillar 4 - Marketing and O2O

| Requirement | Actual state | Required evidence before release |
| --- | --- | --- |
| Multi-touch attribution | Static analytics values | Event schema, identity resolution, attribution test fixtures, reconciliation report |
| POS integrations | No POS adapter | Provider contracts, webhook verification, replay/idempotency tests |
| Behavioral broadcast | Campaigns are local JSON simulations | Consent-aware audience query, queue, throttling, provider receipts, opt-out tests |

**Pillar status:** MISSING as a production capability.

### Pillar 5 - Education Ecosystem

| Requirement | Actual state | Required evidence before release |
| --- | --- | --- |
| Zok Academy and certificates | UI content only | Course/content model, enrollment, completion, certificate verification |
| Template marketplace | No marketplace service or transaction model | Moderation, ownership/license model, versioned publishing, abuse tests |
| Interactive setup wizard | Landing/dashboard empty states only; no persisted wizard | Step state model, resumability, validation and tenant-scoped completion tests |

**Pillar status:** UI PARTIAL; platform capability MISSING.

## 5. Release Gates

### Gate A - Repository and dependency integrity

Run from `/mnt/zok`:

```bash
npm ci
npm audit --omit=dev --audit-level=high
```

Acceptance:

- clean install from the committed lockfile;
- zero production high/critical advisories, or a documented time-bound exception;
- no credentials, runtime DB, dependency directory, or build output in the tracked file set.

### Gate B - Unit and request-path verification

```bash
npm test
npm run lint
npm run typecheck
```

Acceptance:

- authentication fails closed when unconfigured;
- invalid login is generic and does not disclose account state;
- protected data requires a session;
- state-changing requests require a valid origin and CSRF token;
- invalid identifiers and oversized values return 4xx;
- concurrent mutation tests show no truncated JSON or lost update;
- the Vite-compatible TypeScript surface passes without relying on Next types;
- lint has no errors. Warnings require triage before Gold Master.

### Gate C - Build and runtime smoke

```bash
npm run build
NODE_ENV=production npm start
curl -fsS http://127.0.0.1:3005/api/health
```

Acceptance:

- Vite produces `dist/` successfully;
- API binds only to loopback;
- health is 200 with a valid JSON shape;
- Caddy serves `dist/` and proxies `/api/*` without exposing port 3005;
- production cookies have `Secure` and HTTPS is enforced at the edge.

### Gate D - Enterprise release evidence

This gate is NOT satisfied by local tests. It requires:

- external integration contract tests for every claimed channel;
- tenant and RBAC security review;
- PDPA/GDPR data inventory, consent, deletion, export, and retention evidence;
- independent penetration test and remediation report;
- load test at 2x measured peak with latency under the agreed threshold;
- backup restore drill with recorded RPO/RTO;
- support training and operational runbooks;
- monitored production canary and rollback record.

## 6. Remaining Implementation Tracks

### Track 1 - Durable platform foundation

Create PostgreSQL migrations for tenants, users, roles, contacts, conversations, messages, campaigns, integrations, audit events, and consent. Replace the JSON adapter behind an interface, add transaction tests, and move sessions/rate limits to shared storage.

**Exit evidence:** migration up/down test, tenant-isolation test, concurrent write test, backup/restore drill.

### Track 2 - Identity and governance

Replace the single-owner environment credential with an external IdP or a reviewed account service. Add tenant-scoped RBAC, field redaction, API key rotation, audit event persistence, and administrator recovery.

**Exit evidence:** deny-by-default matrix covering every mutation route, session revocation test, audit export, and security review.

### Track 3 - Channel and queue adapters

Define provider-neutral inbound/outbound event contracts. Implement signature verification, idempotency keys, retry/backoff, dead-letter handling, consent checks, rate limits, and delivery receipts for each provider.

**Exit evidence:** provider sandbox contract suite and replay test for every integration; no UI toggle may claim connected until a verified account exists.

### Track 4 - AI policy and evaluation

Move AI decisions server-side. Store prompt/model versions, classify intent and risk, require approval for sensitive actions, redact personal data, enforce knowledge-source citations, and record model cost/latency.

**Exit evidence:** Thai and English evaluation set, guardrail adversarial set, escalation test, budget test, and human approval audit.

### Track 5 - Migration, attribution, POS, and education

Implement streaming import with dry-run and rollback; define event-based attribution; add POS adapters; then build Academy, marketplace, and setup wizard on the durable tenant model.

**Exit evidence:** idempotent migration report, attribution reconciliation, POS replay suite, certificate verification, marketplace moderation test, and wizard resume test.

## 7. 17-Week Execution Sequence

| Phase | Weeks | Deliverable | Gate |
| --- | --- | --- | --- |
| 1 | 1-4 | Durable schema, identity boundary, API contract, metrics baseline | A, B, C |
| 2 | 5-8 | AI policy service, Thai/English evaluation, queue abstraction | B plus AI evaluation |
| 3 | 9-12 | RBAC, tenant isolation, audit, consent and retention | Governance review |
| 4 | 13-16 | Channel/POS adapters, migration, attribution, broadcast worker | Provider and data replay suites |
| 5 | 17 | Academy/marketplace/wizard polish, load, DR, security, support training | D and signed release record |

The phase schedule is a target sequence, not evidence that the phase is complete.

## 8. Residual Risks and Explicit Non-Claims

- The JSON adapter is not durable or horizontally scalable.
- Session state is process-local and all sessions end on process restart.
- The current role is `owner`; granular RBAC is absent.
- The channel integrations and broadcasts are simulations.
- AI responses in UI simulators are keyword-generated, not guarded model output.
- No independent penetration test, load test, DR drill, PDPA/GDPR review, or 99.99% SLA evidence exists in this repository.
- The production audit is clean after removing Next from the canonical runtime, but dev dependency deprecation warnings still require maintenance.
- The Vite production bundle is approximately 690KB minified; code splitting and performance budgets remain before Gold Master.
- Static legacy Next artifacts must not be deployed as if they were the Vite app.
- This directory is not a Git checkout; commit signing, tracked-file review, remote CI execution, and push evidence are not established here.

## 9. Verification Record (2026-08-10)

The following checks were run after the hardening changes:

| Check | Result | Evidence / boundary |
| --- | --- | --- |
| Clean dependency install | PASS | `npm ci --ignore-scripts --offline` completed from `package-lock.json`; `npm ls --depth=0` has no extraneous/invalid packages |
| Request-path tests | PASS | `npm test`: 1 test passed; covers auth, CSRF, CORS, malformed input, concurrent campaigns, atomic temp cleanup, and corrupt-state preservation |
| Lint | PASS | `npm run lint`: zero errors and zero warnings across `src`, `server.js`, `test`, `scripts`, and `vite.config.js` |
| TypeScript checks | PASS | `npm run typecheck`: Vite-compatible `tsconfig.json` passes while excluding only the explicitly noncanonical Next tree |
| Vite build | PASS with warning | `npm run build`: Vite 8.2.1 produced `dist/`; minified client chunk is approximately 690KB |
| Production dependency audit | PASS | `npm audit --omit=dev --audit-level=high`: `found 0 vulnerabilities` |
| Production-shaped start | PASS | `NODE_ENV=production ... npm start` on alternate loopback ports served static HTML and proxied `/api/health` with HSTS, no-store, and security headers |
| Production cookie proof | PASS locally | Production-mode login emitted `Secure`, `HttpOnly`, and `SameSite=Strict` cookies; Caddy/real HTTPS edge remains deployment evidence |
| Production edge proof | PENDING | Caddy/HTTPS route must be verified in the deployment environment; local preview is not edge evidence |
| Git/remote release proof | PENDING | `/mnt/zok` has no `.git` directory, so commit, signature, tracked-file, and GitHub Actions evidence require a real checkout |

The exact `npm start` smoke used alternate ports because listeners already existed on the documented development ports; those existing processes were left untouched.

## 10. Sign-Off Checklist

- [x] Canonical runtime documented as Vite plus Express.
- [x] Hardcoded demo credentials removed.
- [x] Session, CSRF, CORS, rate limit, validation, security headers implemented.
- [x] JSON writes serialized and atomic; corrupt state fails closed.
- [x] API request-path test exists.
- [x] Production dependency audit is part of the release gate.
- [x] README and deployment procedure match the runtime.
- [ ] Durable multi-tenant database and migrations.
- [ ] External IdP, tenant RBAC, audit retention, and consent model.
- [ ] Verified channel/POS integrations and queue workers.
- [ ] AI guardrail/evaluation service and cost enforcement.
- [ ] Migration, attribution, Academy, marketplace, and wizard services.
- [ ] Independent security, load, DR, privacy, and support sign-off.

**Current verdict:** FIXED FOUNDATION / NOT GOLD MASTER. Promote only after every unchecked gate has current evidence.
