# Phase 6 Evidence Matrix

This matrix maps Phase 6 requirements to implementation, workflow, artifact, environment, and remaining approval evidence.

Status definitions use the issue #1 semantics: **VERIFIED**, **IMPLEMENTED**, **PENDING_EXTERNAL**, **PENDING_OPERATOR**, **BLOCKED**, and **DISABLED**.

| Requirement | Implementation or merge evidence | Workflow or artifact evidence | Environment | Status |
|---|---|---|---|---|
| CI tests and dependency policy | PR #5 and subsequent verification merges | Run `29291429851` | GitHub Actions | VERIFIED |
| Secret-pattern and browser credential scan | PR #5, PR #7, PR #10 | Runs `29291429851`, `29292145378` | GitHub Actions | VERIFIED |
| SPDX SBOM and provenance | PR #5 | SBOM artifacts `8295182927`, `8295182600`; provenance on run `29291429851` | GitHub Actions | VERIFIED |
| Seven-service health topology | PR #10, merge `d8207aa1a7880899c1fcea4de5e6903fc140805a` | Smoke artifact `8295434594` | Isolated Compose | VERIFIED |
| Durable agent job, queue, audit, workspace state | PR #5, PR #6 | Restart and persistence checks in final smoke | Isolated Compose | VERIFIED |
| Agent approval, execute, cancel, fail, retry, audit | PR #7, PR #9, PR #10 | Run `29292145378` | Isolated Compose | VERIFIED |
| Workspace Runtime approval boundaries | PR #7 | Staging smoke evidence | Isolated Compose | VERIFIED |
| Billing Ledger idempotency and duplicate rejection | PR #7 | Staging smoke evidence | Isolated Compose | VERIFIED |
| ZWallet prohibited capability rejection | PR #10 | Run `29292145378` | Isolated Compose | VERIFIED |
| ZChat automated accessibility/mobile/session checks | PR #10, PR #11 | Run `29292145378` and subsequent race fix | Isolated Compose | VERIFIED |
| Backup export and restore | PR #5, PR #7 | Isolated deployed smoke | Isolated Compose | VERIFIED |
| External backup target restore | Operator-selected target required | None yet | External staging | PENDING_EXTERNAL |
| Structured logs and Prometheus metrics | PR #5, PR #7 | Isolated deployed smoke | Isolated Compose | VERIFIED |
| Dashboard, distributed traces, alert delivery | Platform selection and deployment required | None yet | External staging | PENDING_EXTERNAL |
| AI non-streaming completion | Gateway evidence request `79a7ce8b-4d50-4ba9-972d-a5d219293b72` | Status `200`, `proxy_success` | Local/staging provider account | VERIFIED |
| Supabase read-only Data API bridge | Phase 6 API authenticated `/supabase/read` route with env-based URL, anon-key, and table selection | Route-level success and failure-path tests in `services/phase6-api/tests/test_supabase_read.py` | Repository / isolated Compose | IMPLEMENTED |
| AI streaming and file upload | Approved upstream account required | None yet | External staging | PENDING_EXTERNAL |
| Multi-provider failover contracts | PR #12 | Deterministic unit and integration tests | Repository | VERIFIED |
| Multi-provider external verification | Agent Control Panel UI and Redis Pool Gateway | Real approved-account evidence absent | External staging | PENDING_EXTERNAL |
| Provider credentials remain server-side | Gateway architecture and automated browser scans | Runs `29291429851`, `29292145378` | Repository/Compose | VERIFIED |
| Actual production browser bundle and HAR inspection | Deployed browser and routing required | None yet | External staging | PENDING_EXTERNAL |
| Cloudflare Access mapping | Agent Control Worker proxy logic and wrangler config | External account and policy mapping absent | External staging | PENDING_EXTERNAL |
| External identity and production claim mapping | Tenant/subject header boundary exists | Authoritative IdP mapping absent | External staging | PENDING_OPERATOR |
| Production secret manager | Local and GitHub Environment handling documented | Vendor and access policy absent | Production | PENDING_OPERATOR |
| Managed DB, queue, object storage, region | Adapter contracts and durable local provider exist | Managed-service evidence absent | Production | PENDING_OPERATOR |
| Human keyboard, screen-reader, and target-device QA | Automated static checks exist | Human test record absent | External staging | PENDING_EXTERNAL |
| Billing currency, tax, jurisdiction, processor | Safety boundary exists | Business/legal decision absent | Production | PENDING_OPERATOR |
| Staging reviewer and review time | Review controls exist | Named completed review absent | External staging | PENDING_OPERATOR |
| Incident owner, escalation, watch window | Incident runbook exists | Named operational record absent | Production | PENDING_OPERATOR |
| Production release approval | Production environment requires approval | Explicit release SHA approval absent | Production | PENDING_OPERATOR |
| Current remote-tracking `main` (`0633655cf1f1c2a83a0eb154d5bafe59fd26fdce`) | Repository head tracking | Local remote ref resolves to PR #115 merge; release-specific external evidence has not been refreshed for this SHA | Repository | PENDING_EXTERNAL |
| Last release-gate evidence (`f37f78387680e8d7cdaad09c6b126c38352f1629`) | Seven-service topology and release gates | Main runs `29625998536`, `29625998526`, `29625998544`, `29625998531`, `29625998548`, and `29625998538` passed | GitHub Actions / isolated Compose | VERIFIED |
| Current `main` security eligibility | CodeQL and Dependabot scanning | CodeQL Advanced run `29468958931` passed; Dependabot alert state was not re-fetched with authenticated API access | GitHub security scanning | IMPLEMENTED |
| Current branch head repo-local validation (`d4b50605058786a800bcd9e8bfaa8d5def481424`) | Cloudflare Terraform state cleanup and latest branch-head validation | `git diff --check`, `node --test scripts/test/codeql-workflow.test.mjs`, `pnpm test`, and the pre-push hook all passed after removing tracked state files and adding stack-local ignore rules | Repository | VERIFIED |
| Remote-tracking `origin/main` helper drift (`0633655cf1f1c2a83a0eb154d5bafe59fd26fdce`) | GitHub environment helper imports `STAGING_REVIEWER`, `INCIDENT_OWNER`, `ESCALATION_ROUTE`, `WATCH_WINDOW`, `PRODUCTION_REVIEWER`, and `PRODUCTION_APPROVER` from the loaded dotenv overlays | `bash -n scripts/configure-github-environments.sh`; `node --test scripts/test/configure-github-environments-script.test.mjs scripts/test/current-head-evidence-sync.test.mjs` | Repository-local validation | IMPLEMENTED |
| Production release record operator context | `production-release-record.yaml` now carries `stagingReviewer`, `incidentOwner`, `escalationRoute`, and `watchWindow` alongside the approval and execution fields | `scripts/test/operator-governance.test.mjs` and `node scripts/validate-release-templates.mjs` | Repository / workflows | IMPLEMENTED |
| Identity-provider and tenant-claim decision record | `scripts/staging-decision-record.json` captures the approved OIDC provider class and claim-mapping reference used by the external staging workflow; `schemas/operations/staging-decision-record.schema.json` captures the expected record contract | `scripts/validate-staging-decision-record.mjs` and `scripts/test/staging-decision-record.test.mjs` | Repository | IMPLEMENTED |
| Phase 6 operator-input register | `scripts/phase-6-operator-inputs.json` captures the remaining Issue #1 `PENDING_OPERATOR` stack as a machine-readable pending contract; `schemas/operations/phase-6-operator-inputs.schema.json` captures the expected record shape | `scripts/validate-phase-6-operator-inputs.mjs` and `scripts/test/phase-6-operator-inputs.test.mjs` | Repository | IMPLEMENTED |
| AI Gateway disconnect-aware upstream cancellation | Branch-local gateway abort handling and disconnect regression test | Deterministic repository-local test coverage on this branch; PR-head workflow artifacts pending | Repository | IMPLEMENTED |
| CodeQL Advanced self-hosted runner lane | Self-hosted runner, broader query suite configuration, and explicit language toolchain setup | Workflow-shape regression test covers `runs-on: [self-hosted, Linux, X64]`, `security-and-quality` config loading, and setup ordering for Node/pnpm/Go/Python analysis | Repository / self-hosted runner | IMPLEMENTED |
| Operator sign-off record coverage | Phase-6 operator input register, operational ownership record, and production release record are linked by workflow-shape and template validation | `scripts/test/operator-governance.test.mjs`, `scripts/test/deployment-readiness-workflows.test.mjs`, `node scripts/validate-release-templates.mjs` | Repository / workflows | IMPLEMENTED |
| Agent Control Panel compose/start evidence (`3bc681f7a288b6a556d3885ee07623c8fb599b34`) | Dedicated Next.js Dockerfile for `apps/agent-control-panel`, compose service wiring, and smoke alignment for the current branch head | `scripts/test/compose-next-service.test.mjs`, `scripts/test/staging-smoke-zchat-markup.test.mjs`, `git rev-parse HEAD`, `docker compose -f compose.yml up -d --build --wait`, `node scripts/staging-smoke.mjs` | Isolated Compose | VERIFIED |

## Release selection rule

A commit may be selected as a production release candidate only when:

1. Its own CI, dependency, secret-scan, SBOM, and provenance results are recorded.
2. External staging tests reference that exact commit or immutable image digest.
3. The staging reviewer records identity and review time.
4. Incident ownership, escalation, watch window, and rollback target are recorded.
5. A production approving operator explicitly approves that exact release.

Prior evidence remains valid for the commits and artifacts it identifies, but it must not be silently transferred to a newer `main` head.
