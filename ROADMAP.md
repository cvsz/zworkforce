# Roadmap

This roadmap tracks shipped release lines and the next repository/operator
work. It does not claim that external production infrastructure exists merely
because manifests or configuration examples are present.

## v1.0.0 — completed

Single-node control plane, agents, model routing, approvals, tools, cost
ledger, dashboard, Docker and CI.

## v2.0.0 — completed

Tenant isolation, durable SQLite lease workers, multi-provider failover, scoped
persistent API keys, four-eyes approvals, per-agent grants, memory, signed
skills, tamper-evident audit, outcome economics and hardened operations.

## v3.0.0 — completed

- PostgreSQL distributed state and `SKIP LOCKED` worker leasing.
- Versioned workflow DAGs.
- Cron/interval scheduling and durable event triggers.
- Service leader leases for scheduler/outbox HA.
- Policy-as-code task/tool enforcement.
- A/B tier evaluation and model optimization evidence.
- Native OIDC and group-role mapping.
- Vault/AWS/file/env secret references.
- Stateless MCP 2026-07-28 management endpoint/client.
- Local/S3 content-addressed artifacts.
- Local/Qdrant semantic memory with OpenAI-compatible embeddings.
- OTLP tracing, Prometheus/Grafana examples.
- SLOs, capacity forecasts, chargeback/showback.
- Agent templates and semantic version snapshots.
- Signed remote skill registry.
- Kubernetes API/worker scaling, PDBs and network-policy baseline.
- Tag-driven release workflow, SBOM, checksums, provenance, GHCR publishing,
  Dependabot, Dependency Review, CodeQL, and production runbooks.

## v3.0.1 — completed

- Hardened response-header construction and static MIME mappings.
- Replaced weak API-key verification with salted PBKDF2-HMAC-SHA256 records.
- Rejected legacy unsalted API-key records so operators must recreate and rotate
  those credentials before upgrading.
- Added secure CLI API-key secret-file output without plaintext stdout leaks.
- Made PostgreSQL integration fixtures repeatable.
- Protected `main` with pull-request, status-check, force-push, and deletion
  controls.

## v3.0.2 — completed

- Added the packaged Windows 11 operator client and Windows client CI.
- Enforced HTTPS for non-local client connections and protected API-key
  transport.
- Made MSIX smoke-test certificate trust cleanup deterministic.
- Documented the production Workforce control-plane endpoint.
- Consolidated Z.A.R.V.I.S. under `packages/zarvis` with package-level CI,
  release governance, API tests, Node workspace tests, and Windows restore
  checks.

## v3.0.3 — repository candidate prepared

- Pruned duplicated/obsolete Z.A.R.V.I.S. product surfaces from the consolidated
  package boundary.
- Enforced owner-only Windows ACLs for generated API-key secret files.
- Fixed release publishing when trusted Windows MSIX signing secrets are absent.
- Added `docs/GITHUB-OPERATIONS.md` for branch, check, alert, release, package,
  GHCR, and cleanup operations.
- Added `docs/PROMETA-MASTER.md` as the master agent, skill and prompt-metadata
  operating model.
- Refreshed the native WinUI zWorkforce shell and Overview control-plane UI.
- Promoted package/module/Makefile/dashboard/Compose/Kubernetes/manual container
  publishing metadata and release documentation to the `3.0.3` candidate.
- Added a dedicated `documentation-contract` CI job for Markdown link and
  repository-policy validation.
- Added `.github/rulesets/main.json` as an API-compatible desired-state default
  branch protection contract and `tests/test_repository_policy.py` to prevent
  required-check drift.
- Excluded path-filtered ZARVIS jobs from global required contexts to avoid
  blocking unrelated pull requests with checks that are never emitted.
- Strengthened `scripts/verify_release.py` to validate GitHub operations,
  package publishing guards, ruleset policy, production evidence paths,
  dashboard/Makefile/deployment version consistency, and required release files.
- Added `docs/PRODUCTION-EVIDENCE.md` to separate CI evidence from real external
  PostgreSQL/PITR, identity, provider, storage, observability, Windows, and
  release-decision evidence.
- Consolidated sub-packages `packages/zsp-aitool` (Shopee Affiliate AI Studio & HyperFrames), `packages/zider` (AI Browser Companion), `packages/zeto` (ProMeta Content Factory & Super Agent Office Suite), and `packages/zarvis` (Realtime Voice Assistant).
- Added master orchestrator and compiled Go CLI toolchain (`control.sh` & `cmd/zctl/`) with service matrix health checks, zero-leak secret masking, and 140-test automated verification.

The immutable `v3.0.3` tag is intentionally **not** created as part of repository
candidate preparation. It is authorized only after the candidate is merged to
`main`, all mandatory checks and reviews are green, the desired GitHub ruleset
is reconciled server-side, mandatory external evidence is recorded, and a GO
decision is approved.

### v3.0.3 release-scope authority

For release triage, the current-release boundary is defined by this `v3.0.3`
section together with `planning/exec-planning-zwf.md` and
`docs/PRODUCTION-EVIDENCE.md`. Required GitHub checks, actionable security
findings, and explicit release-blocking requirements in those sources override
older or broader status labels elsewhere.

Subsystem execution plans are intentionally allowed to continue beyond the
`v3.0.3` candidate. Z.A.R.V.I.S., Zeto, Zider, zsp-aitool, router,
Hermes/Spawn, and Skywork-inspired workspace plans therefore represent
**forward roadmap scope unless an item is explicitly bound to v3.0.3** by the
release sources above. An `Active`, `Production Target`, or similar subsystem
status must not by itself downgrade the `v3.0.3` repository candidate, and it
must not be rewritten to `complete` unless its own documented Definition of
Complete is actually satisfied.

Release-state vocabulary:

- **v3.0.3 required / complete** — implemented and verified repository work in
  the candidate scope;
- **v3.0.3 required / incomplete** — a current release blocker that must be
  resolved before immutable promotion;
- **forward roadmap** — planned or active product work outside the current
  release boundary;
- **external evidence** — operator-owned validation that cannot be inferred
  from repository implementation or CI.

`planning/RELEASE-SCOPE-STATUS.md` is the normalized subsystem classification
overlay for this vocabulary. It does not replace subsystem Definitions of
Complete; it prevents broad feature-plan labels from being misread as current
release blockers or as evidence that forward work is complete.

## Remaining production/operator work

These are external operational concerns, not unimplemented in-process features:

- run the PostgreSQL integration and recovery suite against an operator-owned
  staging/production-equivalent service rather than only GitHub's ephemeral CI
  service;
- prove managed PostgreSQL backups, restore and PITR and record observed RPO/RTO;
- reconcile the checked-in desired GitHub ruleset with the actual repository
  ruleset using administration permission and record the resulting ruleset ID;
- validate production OIDC/credential lifecycle and provider failover;
- validate external S3/Qdrant/OTLP/alert routes when those backends are enabled;
- run HA lease/failure drills for workers, scheduler and outbox;
- validate trusted Windows package signing and live HTTPS operator flow when a
  production MSIX is in scope;
- record immutable image digest, package checksums, owners, rollback target, and
  GO/NO-GO decision in the release evidence record.

## Infrastructure adapters / future compatibility

These remain external deployment concerns rather than fake in-process features:

- managed PostgreSQL HA, PITR, and multi-region replication;
- organization-specific SAML/SCIM lifecycle through an IdP or identity-aware
  proxy;
- provider-specific managed queues when PostgreSQL leasing is not the desired
  queue;
- organization-specific SaaS connectors exposed safely through MCP or approved
  internal gateways;
- cloud-specific ingress, WAF, KMS/HSM, service mesh and egress proxy
  configuration;
- disaster-recovery runbooks tied to the operator's cloud and RPO/RTO.

The platform boundary remains extensible, but zWorkforce does not claim external
infrastructure has been provisioned until credentials, accounts, controls,
drills and sign-offs are recorded for the exact deployment.

## แผนงานระยะถัดไป — ZEAZ Center Control Plane

รายการนี้เป็นแผนงานระยะถัดไป และไม่ใช่ release blocker เว้นแต่เอกสาร release ที่มีอำนาจจะกำหนดให้เป็นส่วนหนึ่งของ candidate อย่างชัดเจน

- [x] กำหนดสัญญา ownership, approval, evidence และ mutation ของ control plane
- [x] เพิ่ม schema สำหรับ inventory ของ repository/hostname และตัวอย่างที่ไม่มี secret
- [x] กำหนด `apps/agent-control-panel` เป็นพื้นฐานหน้า operator ใน browser
- [ ] ทำ read-only GitHub fleet inventory ด้วย GitHub App แบบ least privilege
- [ ] ทำ read-only Cloudflare inventory จาก Terraform ที่ repository เป็นเจ้าของและข้อมูล provider ที่อ่านกลับมา
- [ ] ทำ preview สำหรับ repository generator ที่ใช้ zTemplate
- [ ] ทำการสร้าง repository และ pull request สำหรับ baseline sync หลังอนุมัติ
- [ ] ทำ proposal สำหรับ GitHub ruleset/security mutation พร้อมตรวจ compare-and-set
- [ ] ทำ pipeline สำหรับ Cloudflare Terraform preview/digest/approval/apply ผ่าน repository เจ้าของ
- [ ] เพิ่ม dashboard หลักฐาน production readiness, backup/restore, rollback และ DR
- [ ] เพิ่ม accessibility, browser E2E และการตรวจ role/tenant/session revocation
