# Changelog

## 3.0.4 — 2026-08-25

- Fixed the production container to install the S3 runtime extra used by the S3 artifact backend.
- Replaced the HA API healthcheck's unavailable `curl` dependency with an in-image Python healthcheck.
- Corrected current deployment, installer, dashboard, telemetry, client, and release metadata to the immutable `v3.0.4` patch line.
- Records `v3.0.3` as the published predecessor; production promotion remains gated on the corrected image and external evidence.

## 3.0.3 — 2026-08-17

### Autonomous Control Plane & Subsystems
- **MCP Reverse Tunnel Gateway** (`zworkforce/tunnel.py`): Encrypted localhost-to-cloud reverse tunnel with heartbeat fencing and tenant isolation (PR #117).
- **Zeto QA & SEO Engines** (`packages/zeto/`): 12-point QA evaluation loop with automated $<90$ remediation and multi-platform hashtag/keyword density analysis (PR #117).
- **Zarvis Live Realtime Audio & VAD** (`packages/zarvis/`): Bidirectional Gemini Live PCM16 streaming gateway and adaptive energy VAD tuning (PR #116).
- **OTLP Telemetry & Typed Handoff** (`zworkforce/`): Multi-sink OTLP exporter with secret scrubbing and typed cross-agent delegation contracts (PR #115).
- **Skywork Citation Validator & A2A Manifest** (`zworkforce/`): Deep research citation scoring ($\ge 0.65$) and `/.well-known/agent.json` discovery registry (PR #119).
- **ZSP Collab & ZWF ACP Server** (`packages/zsp-aitool/`, `zworkforce/`): Yjs CRDT real-time multi-user timeline collaboration and complete Agent Client Protocol (ACP) JSON-RPC standard (PR #120).
- **Zider Context Menu & CSP Hardening** (`packages/zider/`): Native browser selection actions and strict Manifest V3 Content Security Policy (PR #118).
- **Zarvis Caption Overlay & zRed Canary** (`packages/zarvis/`, `zworkforce/`): BCP-47 live transcript overlay, CodeQL SARIF CVSS triage, and runtime secret canary leak halting (PR #121).
- **Autonomous Quad-Loop Engine** (`scripts/auto-quad-loop.sh`): Installed cron automation for continuous test, doctor, plan sync, and delivery (PR #114).

### Free-model coding CLI
- Added `zktcoder`: a zero-dependency, stdin-driven coding CLI for the zWorkforce OpenAI-compatible gateway (Claude Fable 5 / DeepSeek V4 and friends) with a model selector, `--list-models`, `--cwd`, and no telemetry.
- Registered the `zktcoder` console script and pointed the `ZworkforceLocalEndpoint` and `zworkforce_code_agent` tool at it (falling back to the legacy `zwf-coder` binary).

### Release readiness and operator experience
- Promoted active Python, Compose, Kubernetes, container-publishing, dashboard, and Makefile metadata to the `v3.0.3` release candidate.
- Refreshed the native WinUI zWorkforce shell and Overview control-plane dashboard while preserving the existing API, event-handler, and view-model contracts.
- Added a dedicated documentation and repository-policy CI gate, a desired-state main-branch ruleset contract, and regression tests for required check contexts.
- Extended release-integrity policy so package, deployment, GitHub operations, package publication, and production evidence paths are checked together.
- Added an explicit production-evidence checklist so environment-dependent PostgreSQL/PITR, identity, provider, object/vector storage, observability, and Windows-client drills cannot be marked complete without operator evidence.

### Dependencies and CI
- Consolidated the August dependency updates for the Z.A.R.V.I.S. API and Node workspace.
- Added a peer-dependency compatibility gate to prevent unsupported ESLint and TypeScript major versions from entering the workspace.
- Enabled Linux restore validation for Windows-targeted Z.A.R.V.I.S. projects and retained the full Windows build, test, package, and smoke gate.
- Removed invalid Dependabot label assignments and documented compatible-major update policy.
- Hardened cross-platform validation, including owner-only Windows ACLs for generated API-key secret files.
- Fixed release publishing when optional trusted Windows MSIX artifacts are skipped.
- Removed release-version magic strings from API and CI contracts where the package metadata can be used as the source of truth.

### Documentation
- Refreshed project, package, release, GitHub contribution, and issue-template documentation for the consolidated `packages/zarvis` layout.
- Added GitHub operations documentation for branch, check, alert, release, package, GHCR, and cleanup procedures.
- Refreshed the production readiness execution plan and roadmap from the `v3.0.2` baseline to the `v3.0.3` release-readiness candidate.

## 3.0.2 — 2026-08-09

### Windows client and operations
- Added the packaged Windows 11 operator client with complete REST service-layer route coverage.
- Enforced HTTPS for non-local client connections and protected API-key transport.
- Made MSIX smoke-test certificate trust cleanup deterministic and verified.
- Documented `https://zwf.zeaz.dev` as the production Workforce control-plane endpoint.

## 3.0.1 — 2026-08-09

### Security and reliability
- Hardened response-header construction and fixed static MIME mappings.
- Replaced weak API-key verification with salted PBKDF2-HMAC-SHA256 records.
- Rejected legacy unsalted API-key records; operators must recreate and rotate
  those credentials before upgrading.
- Added secure mode-0600 CLI secret-file output without plaintext stdout leaks.
- Made PostgreSQL integration fixtures repeatable across test runs.

### Dependencies and operations
- Updated checkout, Python setup, Buildx, image build/push, registry login, and
  Python container dependencies.
- Protected `main` with pull-request, status-check, force-push, and deletion
  controls.

## 3.0.0 — 2026-08-09

### Added
- PostgreSQL distributed backend and `SKIP LOCKED` queue claims.
- Workflow DAGs, schedules, event rules and leader-elected scheduler.
- Policy-as-code runtime enforcement.
- A/B evaluation suites and model-tier optimization summaries.
- Native OIDC, secret-store references and signed remote skills.
- Stateless MCP management endpoint/client.
- Runtime-selectable local/S3 artifact stores.
- Runtime-selectable local/Qdrant semantic memory with embedding adapter.
- OTLP tracing, durable webhook outbox, SLO/capacity/chargeback reporting.
- Agent templates/version history, Kubernetes and observability deployment examples.
- Tag-driven GitHub release pipeline with wheel/sdist, SHA-256 checksums, CycloneDX SBOM, build provenance and GHCR OCI provenance/SBOM.
- Dependabot, dependency review, CODEOWNERS and pull-request security/release checklist.
- Production readiness, release, secret-management and disaster-recovery runbooks.
- Guarded PostgreSQL backup/restore scripts and deployment smoke test.
- Release metadata verifier enforcing package/Compose/Kubernetes version consistency.

### Changed
- Production Compose defaults to PostgreSQL with dedicated API/worker/scheduler services and supports immutable `ZWORKFORCE_IMAGE` overrides.
- Kubernetes release manifests use canonical `v3.0.0` GHCR tags.
- Python dependency floors updated for the v3 distributed/identity stack.
- Dashboard and API surface expanded for automation, evaluation and economics.
- CI now validates operational scripts, release metadata, SBOM generation and production Compose rendering in addition to runtime tests.

### Compatibility
- Existing v2 SQLite data/schema remains supported.
- Existing `/api/v1` task/agent/memory/provider endpoints remain available.

## 2.0.0 — 2026-08-09
Multi-tenant durable runtime, provider failover, scoped identity, approvals, tool policy, memory, signed skills, audit integrity, outcome economics and AI FinOps.

## 1.0.0 — 2026-08-09
Initial production-oriented single-node AI Workforce control plane.
