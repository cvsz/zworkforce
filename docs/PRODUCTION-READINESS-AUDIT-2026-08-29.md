# zWorkforce Production Readiness Audit

**Repository:** `/home/cvsz/platforms/zworkforce`
**Audit Date:** 2026-08-29
**Scope:** Database operations, identity/authorization, network/egress, runtime isolation, observability, error handling/resilience

---

## Executive Summary

The zWorkforce repository demonstrates strong security foundations: parameterized SQL queries dominate the data layer, PBKDF2 key hashing is implemented, policy-as-code and hash-chained audit trails exist, container images run as non-root with `readOnlyRootFilesystem`, and Kubernetes manifests include default-deny NetworkPolicies. However, there are **2 critical** and **6 high/medium** findings that should be addressed before production promotion.

---

## 1. Database Operations

### 1.1 SQL Injection Risk — Risky f-string pattern in `db_finops.py`
- **Severity:** Medium
- **File:** `zworkforce/db_finops.py:40`
- **Observed:** The `spent()` method builds a SQL clause string from `scope_type` and interpolates it into an f-string:
  ```python
  row = c.execute(f"SELECT COALESCE(SUM(cost_credits),0) FROM usage_events2 WHERE {clause} AND created_at>=?", ...)
  ```
  The `clause` is assembled from `"tenant_id=?"`, `" AND department=?"`, or `" AND agent_id=?"` based on `scope_type`.
- **Risk:** Currently the interpolated text is from a controlled set, but this pattern is fragile. If `scope_type` validation ever changes (e.g., new scope types added without updating the if/elif chain), arbitrary SQL could be injected.
- **Expected:** All SQL fragments should be static constants, or the query should be built with strict whitelist validation before interpolation.
- **Suggested Fix:** Replace f-string with a static query map:
  ```python
  _CLAUSE_MAP = {
      "global": "tenant_id=?",
      "department": "tenant_id=? AND department=?",
      "agent": "tenant_id=? AND agent_id=?",
  }
  clause = _CLAUSE_MAP.get(scope_type)
  if clause is None:
      raise ValueError("invalid scope_type")
  ```

### 1.2 PostgreSQL TLS Not Enforced
- **Severity:** High
- **File:** `zworkforce/db_backend.py:130`
- **Observed:** `psycopg.connect(dsn, autocommit=True, row_factory=tuple_row)` is called without enforcing SSL mode.
- **Risk:** If the DSN omits `sslmode=require` or `sslmode=verify-full`, database connections may transmit credentials and data in plaintext over the network.
- **Expected:** Production PostgreSQL connections should enforce TLS.
- **Suggested Fix:** Parse the DSN and enforce `sslmode=require` (or `verify-full`) if not present, or reject non-HTTPS localhost-only connections:
  ```python
  if "sslmode=" not in dsn and not dsn.startswith(("postgresql://localhost", "postgres://localhost")):
      dsn = dsn + "?sslmode=require"
  ```

### 1.3 No PostgreSQL Connection Pooling
- **Severity:** High
- **File:** `zworkforce/db_backend.py:124-131`
- **Observed:** Every `self.connection()` context manager opens a brand new `psycopg.connect()` and closes it on exit. No `ConnectionPool` is used.
- **Risk:** Under concurrent load, the API and worker will exhaust PostgreSQL `max_connections`, causing cascading failures.
- **Expected:** Production services should use bounded connection pooling.
- **Suggested Fix:** Integrate `psycopg.pool.ConnectionPool` and reuse connections across requests. Tune `min_size`/`max_size` to match PostgreSQL limits.

### 1.4 Transaction Boundaries — Mixed autocommit + explicit transactions
- **Severity:** Low
- **File:** `zworkforce/db_backend.py:130`, `zworkforce/db.py:82-113`, `zworkforce/db_base.py:76-83`
- **Observed:** PostgreSQL connections run with `autocommit=True`, so every statement is implicit-commit. Transactional code manually issues `BEGIN` / `COMMIT` / `ROLLBACK`. This is consistent but means any code path that forgets `BEGIN` gets implicit commits.
- **Risk:** Accidental data corruption if a future contributor assumes SQLite-style implicit transactions.
- **Suggested Fix:** Wrap PostgreSQL transactional methods in a `with connection.transaction():` block using psycopg2/psycopg3 transaction context managers, and add a lint rule or test that asserts `BEGIN` precedes multi-statement writes.

### 1.5 Migration Safety — V1 migration lacks idempotency guard
- **Severity:** Medium
- **File:** `zworkforce/db_migration.py:12-106`
- **Observed:** `_migrate_v1_if_needed()` checks `schema_meta` for `v1_copy_complete`, but there is no lock or version check to prevent two processes from running the migration simultaneously.
- **Risk:** Concurrent startup of multiple API/worker instances could run the V1→V2 migration twice, causing duplicate key violations or partial state.
- **Expected:** Migrations should use advisory locks or schema-level locking.
- **Suggested Fix:** Use the existing `_POSTGRES_SCHEMA_LOCK_KEY` advisory lock (already used in `db_base.py:78`) for V1 migrations, or add a SQLite file lock.

---

## 2. Identity and Authorization

### 2.1 API Key Rotation and Revocation — Well Implemented
- **Severity:** N/A (positive finding)
- **Files:** `zworkforce/security.py`, `zworkforce/db_governance.py`, `zworkforce/api.py`
- **Observed:**
  - Keys are created with `zwf_` prefix and PBKDF2-salted hashes.
  - Bootstrap keys can be rotated (upsert revokes old bootstrap keys with the same name).
  - Dynamic keys can be revoked via `/api/v1/api-keys/{id}/revoke`.
  - Legacy SHA256 keys are rejected (`test_security_v2.py:32`).
  - Rate limiting is applied per key.
- **No action required.**

### 2.2 OIDC/JWT Validation — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/identity.py`
- **Observed:**
  - `PyJWKClient` with key caching.
  - Algorithm allowlist restricted to RS/PS/ES/EdDSA.
  - Audience, issuer, and expiry claims are required.
  - HTTPS enforced for remote issuers.
- **No action required.**

### 2.3 RBAC/Scopes Enforcement — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/security.py`, `zworkforce/api.py`
- **Observed:**
  - Four roles: viewer, operator, admin, superadmin.
  - Scope-based authorization with `*` wildcard support.
  - Every mutating endpoint checks `role` and `scope`.
  - `metrics_bearer` is locked to `metrics:read` scope.
- **No action required.**

### 2.4 Four-Eyes Approval — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/db_tasks.py:173-200`, `zworkforce/engine.py:326-329`
- **Observed:**
  - `approval_decision()` prevents self-approval (`actor == task["created_by"]`).
  - Requires `required_approvals` distinct approvals.
  - Mutating tools are blocked until `approved_at` is set.
  - Tests validate two distinct approvals are required.
- **No action required.**

### 2.5 Policy-as-Code — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/policy.py`
- **Observed:**
  - `validate_policy()` enforces schema limits (max 256 rules, 128-char actions).
  - `decide()` supports explicit deny precedence and default-deny.
  - Conditions check `agent_id`, `department`, `actor`, `mutating`, `tier`, `tool`.
  - Policy denials are audit-logged.
- **No action required.**

---

## 3. Network and Egress

### 3.1 HTTP Client Allowlist — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/tools.py:338-355`
- **Observed:**
  - `http_allowlist` restricts outbound hosts.
  - Private/reserved IPs are blocked by default (`http_allow_private=False`).
  - DNS resolution validates resolved IPs against the same allowlist.
  - Mutating HTTP tool is disabled by default.
- **No action required.**

### 3.2 Outbox Redirect SSRF / Data Exfiltration
- **Severity:** Critical
- **File:** `zworkforce/outbox.py:56-59`
- **Observed:** The outbox dispatcher uses `urllib.request.urlopen(req, ...)` directly, which follows HTTP 301/302/303/307/308 redirects automatically. If a webhook destination is compromised or malicious, it can redirect the signed payload to an arbitrary third-party host.
- **Risk:** Webhook payloads (containing tenant-scoped business events) can be exfiltrated to attacker-controlled infrastructure via redirect.
- **Expected:** Outbox deliveries should either not follow redirects, or should validate redirect destinations against the outbox allowlist before following.
- **Suggested Fix:** Use a custom redirect handler (similar to `_NoRedirect` in `tools.py`) that validates `Location` against `allow_hosts` before following, or reject redirects entirely for outbound webhooks.

### 3.3 Outbox Infinite Retry Without Dead-Letter Queue
- **Severity:** Critical
- **File:** `zworkforce/outbox.py:61-64`, `zworkforce/db_automation.py:535-550`
- **Observed:** Failed outbox deliveries are retried with exponential backoff capped at 3600s, but there is no maximum attempt count and no dead-letter transition. `finish_outbox()` keeps resetting status to `pending` indefinitely.
- **Risk:** Permanently failing webhook endpoints (e.g., 410 Gone, DNS NXDOMAIN, persistent 500) cause unbounded retry storms and fill the outbox table, with no operational escape hatch.
- **Expected:** Outbox items should have a bounded retry count (e.g., 10–20 attempts) and transition to a `dead_letter` status with an operator-facing remediation path.
- **Suggested Fix:** Add an `attempts` threshold check in `finish_outbox()`:
  ```python
  if attempts >= MAX_OUTBOX_ATTEMPTS:
      c.execute("UPDATE outbox3 SET status='dead_letter' ... WHERE id=?", ...)
  else:
      c.execute("UPDATE outbox3 SET status='pending', next_attempt_at=?, attempts=attempts+1 ...", ...)
  ```

---

## 4. Runtime Isolation

### 4.1 Container Security — Strong
- **Severity:** N/A (positive finding)
- **Files:** `Dockerfile`, `compose.yaml`, `deploy/kubernetes/api.yaml`
- **Observed:**
  - Non-root user `10001:10001`.
  - `readOnlyRootFilesystem: true`.
  - `cap_drop: ["ALL"]`.
  - `security_opt: ["no-new-privileges:true"]`.
  - `seccompProfile: RuntimeDefault`.
- **No action required.**

### 4.2 Kubernetes Egress Policies Incomplete
- **Severity:** High
- **File:** `deploy/kubernetes/networkpolicy.yaml`
- **Observed:** The manifest defines `default-deny` for Ingress and Egress, but contains no concrete Egress rules to allow PostgreSQL, model providers, OTLP collectors, or outbox destinations. The comment explicitly says: *"Add environment-specific egress policies for PostgreSQL, model providers, OTLP collectors and approved tool destinations. Default deny is intentional."*
- **Risk:** Without explicit egress allowlists, pods cannot reach PostgreSQL, AI providers, or external webhook targets. Alternatively, if the default-deny is not enforced by the CNI plugin, all egress is unrestricted.
- **Expected:** Specific egress rules for PostgreSQL (port 5432), AI provider endpoints, OTLP collector, and approved outbox hosts.
- **Suggested Fix:** Add Egress NetworkPolicies:
  ```yaml
  - egress:
    - to: [{ipBlock: {cidr: "10.0.0.0/8"}}]  # PostgreSQL VPC
      ports: [{protocol: TCP, port: 5432}]
    - to: [{namespaceSelector: {matchLabels: {app: outbox-allowed}}}]  # webhooks
    - ports: [{protocol: TCP, port: 443}, {protocol: TCP, port: 80}]
  ```

### 4.3 Process Sandbox — bubblewrap Available but Unused in API path
- **Severity:** Medium
- **File:** `zworkforce/tools.py:389-412`, `Dockerfile:13`
- **Observed:** The Dockerfile installs `bubblewrap`, but `shell_exec` runs commands via `subprocess.run(..., shell=False)` without `bwrap`. The container's `readOnlyRootFilesystem` and `cap_drop: ALL` provide strong isolation, but if a container breakout occurs, there is no additional filesystem namespace isolation for shell commands.
- **Risk:** A compromised `shell_exec` command could potentially escape the container or access host-level resources if the container runtime is misconfigured.
- **Expected:** `shell_exec` should use `bubblewrap` to provide an additional layer of filesystem and namespace isolation.
- **Suggested Fix:** Wrap shell commands with `bwrap --ro-bind / / --proc /proc --dev /dev --unshare-all --die-with-parent ...`.

---

## 5. Observability

### 5.1 OTLP/Tracing — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/telemetry.py`
- **Observed:**
  - OTLP/HTTP JSON exporter with configurable endpoint and headers.
  - Sensitive attributes are scrubbed before export.
  - Remote OTLP endpoints require HTTPS (except localhost).
  - Telemetry failures are silent and never disrupt task execution.
- **No action required.**

### 5.2 Metrics Exposure — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/metrics.py`
- **Observed:**
  - Prometheus metrics exposed at `/metrics` behind `viewer` + `metrics:read` auth.
  - Gauges for active tasks, dead letters, success rate, provider health, SLOs.
- **No action required.**

### 5.3 Log Redaction — Good Coverage with Gaps
- **Severity:** Medium
- **Files:** `zworkforce/security.py:183-198`, `zworkforce/providers.py:269-275`, `zworkforce/tools.py:381`
- **Observed:**
  - `redact()` in `security.py` redacts dict keys containing secret/token/password/api_key.
  - `_clean_error()` in `providers.py` strips Bearer tokens and API keys from provider error responses.
  - Tool event args are redacted before storage (`redact(args)`).
- **Gap:** The `redact()` function checks key names but does not redact values that happen to be secrets when the key name is non-obvious (e.g., `{"x": "sk-abc123..."}`). Also, `str(exc)` in `engine.py:352` and `api.py:586` may include internal file paths or stack traces that leak architecture details.
- **Suggested Fix:** Add value-pattern redaction for high-entropy tokens (e.g., `sk_`, `zwf_`, UUID-shaped strings) in `redact()`, and ensure production error responses never include `str(exc)`.

### 5.4 Audit Trail — Complete and Hash-Chained
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/db_governance.py:12-40`
- **Observed:**
  - Every mutation, approval, policy denial, and tool event is audit-logged.
  - Hash chain with `prev_hash` and `event_hash` (SHA-256).
  - `verify_audit_chain()` provides cryptographic integrity verification.
  - Tests validate migration of legacy audit events into the chain.
- **No action required.**

---

## 6. Error Handling and Resilience

### 6.1 Information Leakage in Error Messages
- **Severity:** Medium
- **File:** `zworkforce/api.py:109-113`, `zworkforce/engine.py:352,391-395`
- **Observed:** The API `_error()` method suppresses details in production (`app.settings.env != "production"`), but `engine.py` logs `str(exc)[:500]` into the database and audit trail. Provider errors, subprocess tracebacks, and internal paths can surface in task error fields.
- **Risk:** Tenant users and support staff can see internal stack traces, binary paths, and provider error bodies that reveal implementation details.
- **Expected:** All externally visible error fields should be scrubbed to a safe, user-actionable message.
- **Suggested Fix:** Introduce a `sanitize_error(error: str) -> str` helper that strips stack traces, file paths, and internal tokens, and use it before persisting `error` to tasks and audit events.

### 6.2 Circuit Breaker — Well Implemented
- **Severity:** N/A (positive finding)
- **File:** `zworkforce/db_governance.py:205-216`, `zworkforce/providers.py:224-248`
- **Observed:**
  - `provider_health2` tracks consecutive failures.
  - `open_until` timestamp prevents routing to circuit-open providers.
  - Configurable `provider_circuit_failures` and `provider_circuit_seconds`.
  - Provider pool skips circuit-open providers and falls back to alternatives.
- **No action required.**

### 6.3 Retry/Timeout Bounds — Well Bounded
- **Severity:** N/A (positive finding)
- **Files:** `zworkforce/providers.py:136-165`, `zworkforce/config.py`
- **Observed:**
  - Provider retries: bounded by `retries` (default 2) with exponential backoff capped at 5s.
  - HTTP tool: bounded by `tool_timeout_seconds` (default 30s) and `http_max_redirects` (default 2).
  - Task max attempts: bounded by 10.
  - Doom-loop detection prevents identical tool call repetition.
- **No action required.**

### 6.4 Dead-Letter Queue for Tasks — Adequate
- **Severity:** N/A (positive finding with minor note)
- **File:** `zworkforce/db_tasks.py:137-160`
- **Observed:**
  - Tasks transition to `dead_letter` when `attempt >= max_attempts` or lease expires.
  - Dead-letter tasks are visible in metrics and can be manually retried via `/api/v1/tasks/{id}/retry`.
  - No automated DLQ processing, but manual remediation exists.
- **Minor note:** Consider adding an operator endpoint or scheduled job to alert on dead-letter accumulation.

---

## Severity Summary

| Severity | Count | Findings |
|----------|-------|----------|
| Critical | 2 | Outbox redirect SSRF; Outbox infinite retry without DLQ |
| High | 4 | PostgreSQL TLS missing; No connection pooling; K8s egress incomplete; SQL injection pattern risk |
| Medium | 4 | Migration concurrency; Process sandbox unused; Error message leakage; Log value-pattern redaction gaps |
| Low | 1 | Transaction boundary fragility |

---

## Top Remediation Priorities

1. **Block outbox redirects** — Outbox webhooks must not follow attacker-controlled redirects.
2. **Add outbox DLQ** — Bounded retries (e.g., 20 attempts) then move to `dead_letter`.
3. **Enforce PostgreSQL TLS** — Reject or upgrade unencrypted DSNs in production.
4. **Add connection pooling** — Integrate `psycopg.pool` to prevent `max_connections` exhaustion.
5. **Complete K8s egress policies** — Whitelist PostgreSQL, AI providers, and OTLP destinations.
6. **Fix `db_finops.py` SQL pattern** — Replace f-string clause with a static query map.
7. **Sanitize error messages** — Strip internal paths and stack traces before persisting to DB/audit.
8. **Lock V1 migration** — Use advisory locks to prevent concurrent migration runs.
