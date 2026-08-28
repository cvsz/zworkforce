# Deep upgrade audit: zcoder v1.36.0

Date: 2026-07-26
Target: ZeaZ Provider v0.3.0
Input: `zcoder-v1_36_0.zip`
Method: clean-room behavioral and architectural inventory. No source is to be
copied into ZeaZ Provider.

## Executive decision

Do not merge zcoder into the gateway and do not use it as a source-code base.
It is a 22,144-line single-process Anthropic CLI with a 2,162-line argument
dispatcher. ZeaZ Provider is a network gateway with three compatibility
surfaces and a provider-neutral routing contract. Combining them would couple
request translation, provider reliability, local agent execution, UI,
organization administration, and mutable user state into one trust boundary.

Use zcoder only as a behavioral inventory. Adopt these patterns through a new
implementation:

1. Typed provider failures and retry classification.
2. Per-provider resilience policy with jitter, `Retry-After`, and circuit
   breaking.
3. Dynamic model capability discovery with a short-lived offline cache.
4. Capability-aware request validation before provider calls.
5. Stable correlation IDs, structured audit events, and secret redaction.
6. Dry-run-by-default for destructive control-plane operations.
7. Batch, Files, model lifecycle, usage, and health as optional control-plane
   modules.

Keep local code execution, hooks, skills, plugins, sessions, projects, office
document tooling, TUI, and web UI outside the provider process.

## Inventory

The archive contains 170 entries and no path-traversal entries or symbolic
links. Static parsing found:

| Measure | Value |
|---|---:|
| Production Python files | 67 |
| Production Python lines | 22,144 |
| Test files | 27 |
| Test lines | 5,316 |
| AST test functions | 394 |
| Syntax errors | 0 |
| Declared release test result | 477 passing |

The declared 477 count was not independently executed because the supplied
tree is untrusted executable code and contains subprocess, shell, network,
filesystem deletion, and archive extraction paths. Static inspection is
sufficient for this clean-room inventory.

## Architectural comparison

| Area | zcoder v1.36.0 | ZeaZ Provider v0.3.0 | Upgrade decision |
|---|---|---|---|
| Primary role | Anthropic CLI/agent client | Multi-provider API gateway | Preserve separation |
| Entrypoint | 2,162-line `argparse` dispatcher | FastAPI service | Do not port dispatcher |
| API protocol | Mostly Anthropic-specific | Anthropic Messages, OpenAI Chat and Responses | Preserve ZeaZ contract |
| Provider abstraction | Anthropic modules and raw HTTP | Provider client plus route targets | Expand ZeaZ abstraction |
| Fallback | Model/refusal-specific paths | Ordered provider/model fallback | Add reason-aware policy |
| Resilience | Typed errors, retries, jitter, circuit breaker | Retryable flag and route fallback | Reimplement in core |
| Capability model | Large hard-coded catalog plus live Models API | Static configured aliases | Add dynamic registry |
| State | Flat JSON under home, no writer locking | YAML/env configuration | Keep gateway stateless |
| Agent execution | Shell, hooks, plugins, tools, sessions | None | Separate optional service |
| Control plane | Admin, compliance, files, batches, WIF | None | Optional packages only |
| Observability | Structured local logs and metrics | Health endpoints | Add OpenTelemetry-style events |
| Updates | Source/venv oriented Make targets | HTTPS manifest + SHA-256 + atomic switch | Keep ZeaZ updater |

## Verified high-severity findings in the reference

### P0: the v1.36.0 model-gate fix is still stale

`docs/48_upgrade_v1.36.0_mid_system_gate_fix.md` says Opus 5 is not supported
for mid-conversation system messages. `claude_cache.py` consequently defines
the supported set without `claude-opus-5`.

Anthropic's current Messages documentation and Opus 5 migration guide state
that Claude Fable 5, Claude Mythos 5, Claude Opus 4.8, and Claude Opus 5
support a system-role message after a user turn, subject to placement rules.

This is evidence that a hand-maintained Boolean/model-set matrix becomes stale
even under a documented audit process. ZeaZ must not copy these constants.
Use:

- account-aware live Models API discovery when a provider supports it;
- a versioned capability schema;
- bounded-TTL cache with provenance and observation time;
- a conservative static fallback;
- explicit pass-through mode for unknown future parameters;
- conformance tests generated from capability fixtures.

### P0: plugin archive extraction permits path escape

`claude_plugins.py` fetches or opens ZIP files and calls `extractall()` at
multiple installation paths without first proving every resolved member stays
inside the destination and without rejecting symbolic links or limiting total
expanded bytes. HTTPS-only validation does not make archive content trusted.

ZeaZ Provider must not add in-process plugin installation. A future plugin
manager must:

- download to an unprivileged staging directory;
- require a signed manifest and content digest;
- reject absolute paths, `..`, links, devices, duplicate normalized paths,
  excessive entry count, and expansion-ratio/total-size violations;
- publish atomically after validation;
- run plugin code in a separate, least-privileged process.

### P0: arbitrary shell execution is inside the CLI trust boundary

Shell execution occurs with `shell=True` in agent commands, hooks, settings,
and MCP/subprocess paths. Some calls are intended features, but string-based
shell execution makes the permission layer the sole protection against
command injection.

Never move this into the API gateway. A ZeaZ execution service must use an
argument vector, immutable approval record, workspace allow-list, container
or microVM boundary, restricted network, resource limits, and append-only
audit records. It must be disabled by default.

### P1: circuit breaker counts permanent failures

The retry wrapper calls `breaker.on_failure()` for every `AICoderError` before
checking `RETRYABLE`. Repeated authentication, validation, or other permanent
failures can therefore open the dependency circuit and temporarily block
otherwise valid calls.

ZeaZ should count only downstream transient failures and rate-limit failures
toward provider health. Client 4xx errors, authorization failures, safety
refusals, and unsupported-capability errors must be separate dimensions.

### P1: URL validation does not prevent SSRF

The central URL validator enforces only the `https` scheme. It does not block
loopback, private, link-local, multicast, metadata-service, or DNS-rebinding
targets and does not revalidate redirects. Arbitrary fetch and marketplace
paths therefore need a stronger egress policy.

For ZeaZ, user-controlled URL fetching belongs in an isolated fetch service
with DNS/IP checks on every connection, redirects disabled or revalidated,
host allow-lists where possible, response-size limits, content-type policy,
and no access to cloud metadata or the control network.

### P1: release/security metadata is internally inconsistent

- `SECURITY.md` lists only 1.16.x as supported while the package is 1.36.0.
- It claims `.github/workflows/ci.yml` runs Bandit, but no `.github` workflow
  is present in the supplied archive.
- `requirements.txt` uses minimum versions rather than a lock or hashes while
  the security document calls this dependency pinning.
- Project metadata and runtime dependencies are split between
  `pyproject.toml` and requirements files; the package metadata itself does
  not declare runtime dependencies.

ZeaZ releases should generate one machine-readable version, SBOM, provenance,
locked dependency set, checksums, and a release validation report.

### P1: flat JSON state has no concurrency contract

The reference architecture explicitly documents no concurrent-writer safety.
That is acceptable for a local single-user CLI but not for a multi-worker
gateway or control plane. ZeaZ should remain stateless in the request path.
Mutable control-plane data requires transactional storage, optimistic
concurrency, audit history, and idempotency keys.

### P2: error strings are part of the legacy API

The core generator converts typed failures back into printable strings.
That preserves CLI compatibility but destroys reliable machine-readable error
handling. ZeaZ should retain a stable error envelope and map it independently
to Anthropic and OpenAI error shapes.

## Feature disposition

### Provider-core candidates

| Capability | Priority | ZeaZ implementation |
|---|---:|---|
| Typed error taxonomy | P0 | Provider, policy, upstream, auth, quota, timeout and protocol errors |
| Retry/backoff | P0 | Async, jittered, deadline-aware, honors bounded `Retry-After` |
| Circuit breaking | P0 | Per provider/region; transient errors only |
| Capability registry | P0 | Live discovery + TTL cache + static conservative fallback |
| Request capability validation | P0 | Validate thinking, tools, context, output and streaming before dispatch |
| Model lifecycle | P0 | Active/deprecated/retired state and migration hints |
| Structured logs | P0 | Correlation/request IDs with secret and prompt redaction |
| Usage/cost events | P1 | Normalized token fields; no billing claims without provider source |
| Batch proxying | P1 | Provider extension namespace before cross-provider normalization |
| Files proxying | P1 | Separate endpoints, strict limits, malware/content policy |
| Prompt caching pass-through | P1 | Preserve provider-native fields and headers safely |
| Refusal-aware fallback | P1 | Policy-controlled; never silently weaken safety policy |
| Admin/Compliance proxy | P2 | Separate deployment, credentials and authorization boundary |

### Separate agent-runtime candidates

- Tool execution and approval engine
- Hooks and plan mode
- MCP clients and tunnels
- Local skills and agents
- Project/session/memory stores
- Git/GitHub workflows
- Research, RAG and browser fetching
- Plugins and marketplaces
- Office document features
- TUI and web console

These may consume ZeaZ's Anthropic/OpenAI-compatible API, but must not execute
inside the gateway process.

### Reject

- Copying model names, price tables, beta headers, or capability sets as
  timeless constants
- A single mega-CLI dispatch file
- Plaintext high-privilege credential storage
- `shell=True` execution in the gateway
- Unverified ZIP installation
- Flat JSON as shared service state
- Returning error text as the programmatic contract
- Automatic fallback on all failures

## Proposed ZeaZ v0.4 work packages

### WP1 — Reliability kernel (P0)

Create `errors.py`, `resilience.py`, and a provider health state machine.
Apply a total request deadline, per-attempt timeout, jittered retry, bounded
`Retry-After`, and provider circuit breaker. Fallback only when policy permits
the classified failure. Add deterministic clock/random injection for tests.

Acceptance:

- permanent 4xx never retries and never opens the circuit;
- transient 5xx and network failures retry within the total deadline;
- a successful half-open probe closes the circuit;
- streaming failures before first byte may fail over; failures after emitted
  bytes terminate with a protocol-correct error rather than replaying output.

### WP2 — Capability registry and model lifecycle (P0)

Add provider capability adapters and cache capability observations with
source, provider account, model, region, observation time, and expiry.
Introduce stable aliases such as `zeaz-claude`, but resolve them against the
registry rather than a frozen vendor ID.

Acceptance:

- Opus 5 mid-conversation system support is represented from live or
  current fixture data;
- unavailable/limited-access models are not advertised for an account;
- unknown new fields can be passed through under explicit policy;
- retired models produce a migration error before the upstream call.

### WP3 — Protocol conformance (P0)

Build fixture-driven tests for Anthropic Messages, OpenAI Chat Completions,
and OpenAI Responses: text, images, system/developer roles, tool calls and
results, JSON/structured output, token usage, finish/stop reasons, errors,
and SSE event order.

Acceptance:

- no cross-protocol streaming route returns the current “not enabled” error;
- fallback uses the correct provider-specific model on both streaming and
  non-streaming paths;
- all response IDs, model aliases, usage and stop reasons obey the exposed
  protocol.

### WP4 — Security and observability (P0/P1)

Add request IDs, structured audit events, log redaction, trusted proxy
configuration, rate limits, security headers, body/response limits, and
optional OpenTelemetry export. Separate prompts/content from operational
logs by default.

### WP5 — Optional control plane (P1/P2)

Implement Files, Batches, usage and model discovery as isolated modules.
Admin and Compliance functions require a separate deployment profile,
credential namespace, role policy, immutable audit events, and dry-run
confirmation for destructive operations.

## Release gates

Every upgrade must pass:

1. Unit and protocol-contract tests.
2. Offline provider fixtures for each supported protocol.
3. Optional live smoke tests using restricted test keys.
4. Ruff, type checking, Bandit/Semgrep, dependency audit, secret scan.
5. Container build, non-root runtime, read-only root filesystem test.
6. SBOM and vulnerability scan.
7. Installer dry-run, install, update, rollback and interrupted-update tests.
8. ZIP traversal/bomb/link tests for any archive handling.
9. Version consistency across package, image, manifest and changelog.
10. Documentation provenance date for volatile provider capabilities.

## Immediate implementation order

1. WP1 reliability kernel.
2. WP2 capability registry.
3. WP3 full streaming/protocol conformance.
4. WP4 rate limiting, audit and telemetry.
5. Files and Batches extensions.
6. Separate `zeaz-agent` design only after the gateway release gates pass.

This ordering extracts the strongest behaviors from the reference without
importing its monolith, stale hard-coded capability gates, or execution
risks into ZeaZ Provider.
