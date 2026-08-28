# Current-Head Evidence Record - 2026-07-15

## Baseline

- Current `main` SHA: `2db36e428fa95457e0559dabc224b7d8ff10d289`
- Environment: GitHub Actions and repository-local isolated Compose
- Recorded at: `2026-07-15T15:20:57Z`
- External and production traffic: **DISABLED**

## Classification

| Check | Status | Command or workflow | Result | Artifact | Limitation |
|---|---|---|---|---|---|
| Node/Python validation | VERIFIED | `CI` run `29425990792` | success | None | Repository-local only. |
| Secret/browser scan | VERIFIED | `validate` run `29425992713`, job `87388407955` | success | None | Pattern scanning does not supersede open CodeQL or Dependabot findings. |
| Compose build | VERIFIED | `validate` run `29425992713`, job `87388408351` | success | None | Does not prove external health. |
| SBOM | VERIFIED | `validate` run `29425992713`, job `87388408008` | success | `z-platform-sbom` ID `8347268150`, digest `sha256:aa9cca3bfb86be6f368019d1ce7b4d5930b5d4596d03d716c48e6ddb03d02c29`; `z-platform-sbom.spdx.json` ID `8347267792`, digest `sha256:e98b7e6284dc6458db6ae4b0db89acd57208eaa04c19c7cd5d9a21d578354bbf` | Bound only to the baseline SHA. |
| Provenance policy | VERIFIED | `operations` run `29425992683` | success | `sbom-spdx-json` ID `8347266561`, digest `sha256:2ccbea7d556d8c5d1de538db418697db453f16d35ebacc8fbb32de7c1f5a11a6` | Bound only to the baseline SHA. |
| Deployed smoke | VERIFIED | `validate` run `29425992713`, job `87388407954` | success | `staging-smoke-evidence` ID `8347285839`, digest `sha256:6d51c96fdd373274d428217f8e8860b32ebecda442414474c35c92ca5b612ef6` | Isolated Compose, not external staging. |
| CodeQL workflow | VERIFIED | `CodeQL Advanced` run `29425992884` | success | None | Workflow success does not close existing alerts. |
| Security alert state | BLOCKED | CodeQL and Dependabot APIs | Five CodeQL and one Dependabot alert open | None | The named findings must be remediated and rescanned. |

## Historical remediation evidence

- **IMPLEMENTED** - `npm start` now resolves to `node index.js`.
- **IMPLEMENTED** - The Gateway uses Node 20's built-in `fetch`, eliminating the undeclared runtime import.
- **IMPLEMENTED** - Runtime dependencies use `npm ci` with a committed lockfile in the dedicated Gateway image.
- **VERIFIED** - `npm test` passes the Gateway startup, health, authentication-denial, and log-redaction static contracts locally.
- **VERIFIED** - `docker compose config --quiet` passes locally.
- **VERIFIED** - `docker compose up -d --build --wait` reaches healthy state locally.
- **VERIFIED** - The Gateway startup remediation is included in `2db36e428fa95457e0559dabc224b7d8ff10d289` and its SHA-bound deployed smoke succeeded.

## Current remediation classification

- **IMPLEMENTED** - CodeQL alerts 1-5 are addressed by path containment, rate limiting, default-deny CORS, and command-argument omission with deterministic tests.
- **IMPLEMENTED** - Dependabot alert 1 is addressed by resolving PostCSS to patched version `8.5.19` with a workspace override.
- **BLOCKED** - Verification requires PR-head CodeQL, dependency audit, validation, and immutable artifact evidence for the exact remediation SHA.

No external infrastructure, operator identity, production approval, or production traffic is claimed by this record.

## Branch-head evidence

- Branch head: `beea8189fd40baf299b30838ff7d21a1c81f5abe`
- Environment: repository-local isolated worktree and GitHub Actions workflow shape validation
- Recorded at: `2026-07-16T00:00:00Z`
- External and production traffic: **DISABLED**

| Check | Status | Command or workflow | Result | Artifact | Limitation |
|---|---|---|---|---|---|
| CodeQL workflow hardening | VERIFIED | `node --test scripts/test/codeql-workflow.test.mjs` | success | None | Repository-local workflow-shape validation only. |
| CodeQL workflow YAML | VERIFIED | `python3` YAML parse of `.github/workflows/codeql.yml` | success | None | Workflow structure only; no CodeQL scan was run on this branch head. |
| Documentation sync | VERIFIED | `git diff --check` and repo pre-push validation | success | None | Sync evidence only; no external staging or operator approval is claimed. |

The branch-head record is intentionally separate from the older `main` baseline because its evidence is repository-local only and does not replace immutable deployed evidence for a release candidate SHA.
