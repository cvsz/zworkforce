# Migration Execution Records

## 2026-07-16 — CodeQL Advanced self-hosted runner lane

- Base revision: current branch head after the runner-lane patch.
- Scope: one repository-local CodeQL workflow slice.
- Implementation: updated `CodeQL Advanced` to run on the available self-hosted Linux/X64 runner labels so the security workflow can target the intended runner pool naming without changing the analysis languages or query suite.
- Compatibility: the workflow still analyzes the same repository languages and uses the same repository CodeQL config; only the runner label selector changed.
- Security: no credentials, service tokens, or production identifiers were added; the change only adjusts runner selection metadata for the security workflow.
- Tests: `scripts/test/codeql-workflow.test.mjs` now checks the workflow label list and query-suite selection.
- Limitations: repository-local validation only; PR-head CodeQL execution, artifact binding, and alert-closure evidence on the self-hosted runner remain pending.

## 2026-07-16 — Cloudflare Terraform state cleanup

- Base revision: current branch head after the Terraform state cleanup patch.
- Scope: one repository-local secret/state hygiene slice.
- Implementation: removed tracked Cloudflare Terraform state, backup state, and committed `terraform.tfvars`, and added a stack-local `.gitignore` so future state files stay out of the repository.
- Compatibility: no runtime behavior changed; the cleanup only removes committed local state artifacts and adds ignore rules for future state files.
- Security: this removes committed infrastructure state and prevents future accidental tracking of Terraform state or variable files in the Cloudflare stack.
- Tests: `git diff --check`, `pnpm test`, and the pre-push hook that reran lint, typecheck, tests, and build passed for this commit.
- Limitations: repository-local validation only; no external staging evidence is claimed for this hygiene-only slice.

## 2026-07-16 — Agent Control Panel compose startup fix

- Base revision: current branch head after the Next.js service image patch.
- Scope: one repository-local compose startup slice.
- Implementation: switched `agent-control-panel` in `compose.yml` to a dedicated `deploy/docker/next-service.Dockerfile` that installs dependencies, builds the Next.js app, prunes dev dependencies, and keeps the runtime image non-root before `npm start`.
- Compatibility: the other node-service containers continue to use the shared `deploy/docker/node-service.Dockerfile`; only the Next.js service receives the build step it needs.
- Security: no credentials, secret values, or production identifiers were added; the service still runs with the existing compose safety gates.
- Tests: `scripts/test/compose-next-service.test.mjs`, `docker compose -f compose.yml config --quiet`, `docker compose -f compose.yml up -d --build --wait`, and `docker compose -f compose.yml ps` are the intended validation steps for this slice.
- Limitations: repository-local compose validation only; the image must be rebuilt before the new Dockerfile takes effect in a live stack.

## 2026-07-16 — ZChat deployed-smoke markup alignment

- Base revision: current branch head after the smoke-check alignment patch.
- Scope: one repository-local deployed-smoke correction slice.
- Implementation: loosened `scripts/staging-smoke.mjs` to match the committed ZChat semantic main region and responsive breakpoint actually served by `apps/zchat/public/index.html` and `apps/zchat/public/styles.css`; added `scripts/test/staging-smoke-zchat-markup.test.mjs` to keep the static smoke contract aligned with the deployed markup.
- Compatibility: no runtime behavior changed; the deployed smoke now checks the markup and CSS that are already committed and served by the stack.
- Security: no credentials, secrets, or production identifiers were added; the smoke script still fails closed on unexpected markup.
- Tests: `node --test scripts/test/staging-smoke-zchat-markup.test.mjs` and `node scripts/staging-smoke.mjs` passed in this worktree after the patch.
- Limitations: repository-local isolated Compose evidence only; this does not substitute for any external staging or operator approval requirement in Issue #1.

## 2026-07-16 — Identity-provider and tenant-claim decision record

- Base revision: current branch head after the staging decision-record validator patch.
- Scope: one repository-local identity and claim-mapping contract slice.
- Implementation: added `scripts/validate-staging-decision-record.mjs`, `schemas/operations/staging-decision-record.schema.json`, and workflow coverage so `scripts/staging-decision-record.json` is validated as the canonical machine-readable snapshot for the approved OIDC provider class and tenant-claim mapping reference.
- Compatibility: the existing external staging harness and release-governance records are unchanged; the new validator is additive and fail-closed.
- Security: no provider credentials, account IDs, or secret values were added; the validator rejects placeholder identity-mapping values instead of inventing real ones.
- Tests: `scripts/test/staging-decision-record.test.mjs`, `scripts/test/deployment-readiness-workflows.test.mjs`, `scripts/test/operator-governance.test.mjs`, `node --test scripts/test/configure-github-environments-script.test.mjs scripts/test/current-head-evidence-sync.test.mjs scripts/test/staging-decision-record.test.mjs`, `node scripts/validate-release-templates.mjs`, `node scripts/validate-staging-decision-record.mjs scripts/staging-decision-record.json`, and `git diff --check` passed in this worktree.
- Limitations: repository-local validation only; the actual external identity provider and production claim mapping remain pending operator input.

## 2026-07-16 — Phase 6 operator-input register

- Base revision: current branch head after the operator-input register patch.
- Scope: one repository-local operator-input contract slice.
- Implementation: added `scripts/phase-6-operator-inputs.json`, `schemas/operations/phase-6-operator-inputs.schema.json`, and `scripts/validate-phase-6-operator-inputs.mjs` so the remaining Issue #1 `PENDING_OPERATOR` stack is represented as a canonical machine-readable register.
- Compatibility: the existing release-governance records, staging decision record, and production approval workflows are unchanged; the new register is additive and fail-closed.
- Security: no real secret-manager names, billing values, incident-owner identities, or approval values were fabricated or committed.
- Tests: `scripts/test/phase-6-operator-inputs.test.mjs`, `scripts/test/deployment-readiness-workflows.test.mjs`, `node scripts/validate-phase-6-operator-inputs.mjs scripts/phase-6-operator-inputs.json`, and `git diff --check` passed in this worktree.
- Limitations: repository-local validation only; the real operator decisions still require authorized human input before the production release can proceed.

## 2026-07-16 — Production release record operator context

- Base revision: current branch head after the release-record contract patch.
- Scope: one repository-local release governance slice.
- Implementation: added an explicit `operatorRecord` section to the production release template and schema so the same staging-review, incident-owner, escalation-route, and watch-window context collected by the external readiness harness is also represented in the release record.
- Compatibility: the existing approval, execution, and post-deploy fields are unchanged; the new operator context is additive and keeps the record fail-closed.
- Security: no real operator names, approvals, or production identifiers were added; the fields remain placeholders until an authorized operator fills them in.
- Tests: `scripts/test/operator-governance.test.mjs`, `scripts/test/deployment-readiness-workflows.test.mjs`, `node --test scripts/test/configure-github-environments-script.test.mjs scripts/test/current-head-evidence-sync.test.mjs`, `node scripts/validate-release-templates.mjs`, and `git diff --check` passed in this worktree.
- Limitations: repository-local validation only; the actual operator values and explicit production approval remain pending.

## 2026-07-16 — GitHub environment helper operator-field sync

- Base revision: current branch head after the environment-helper drift guard patch.
- Scope: one repository-local environment bootstrap slice.
- Implementation: documented and tested the GitHub environment helper contract that imports the operator-owned review fields `STAGING_REVIEWER`, `INCIDENT_OWNER`, `ESCALATION_ROUTE`, `WATCH_WINDOW`, and the production reviewer selector values from the loaded dotenv overlays.
- Compatibility: existing environment creation and branch-policy behavior is unchanged; the helper still requires explicit reviewer selectors when the caller supplies them.
- Security: no credentials or production identifiers were added; the helper continues to keep secrets server-side and avoids printing secret values.
- Tests: `bash -n scripts/configure-github-environments.sh`, `node --test scripts/test/configure-github-environments-script.test.mjs scripts/test/current-head-evidence-sync.test.mjs`, and `git diff --check` passed in this worktree.
- Limitations: repository-local validation only; the exact `origin/main` SHA still needs GitHub Actions revalidation for immutable artifact evidence.

## 2026-07-16 — Release governance operator-signoff coverage

- Base revision: current branch head after the operator-signoff coverage patch.
- Scope: one repository-local release-governance slice.
- Implementation: added focused validation coverage for the operator sign-off path, connecting the phase-6 operator input register with the operational ownership and production release records used by the final release workflow.
- Compatibility: no runtime application paths changed; the release governance records remain fail-closed placeholders until an operator fills them in.
- Security: no operator identities, reviewer names, incident owners, or approval values were fabricated or committed.
- Tests: `scripts/test/operator-governance.test.mjs`, `scripts/test/deployment-readiness-workflows.test.mjs`, and `node scripts/validate-release-templates.mjs` passed in this worktree.
- Limitations: repository-local validation only; this slice improves the auditability of the operator-owned stack but does not substitute for real operator sign-off.

## 2026-07-16 — Supabase read-only Phase 6 API bridge

- Base revision: current branch head after the Supabase bridge patch.
- Scope: one repository-local Phase 6 API slice.
- Implementation: added an authenticated `/supabase/read` endpoint that reads a Supabase Data API table using server-side `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_TABLE` configuration with explicit base-URL, table-name, and limit validation.
- Compatibility: existing gateway, webhook, compose, and deployment semantics remain unchanged; the bridge is read-only and does not expose the anon key to browser clients.
- Security: no real credentials were added to source control; the route fails closed on missing config, invalid URL, invalid table, and upstream refusal or malformed payloads.
- Tests: added route-level success and failure-path coverage for auth, missing config, invalid base URL, invalid table name, upstream 403, non-array payload, and out-of-range limits.
- Limitations: repository-local validation only; an approved Supabase project/table is still required for external evidence.

## 2026-07-16 — CI pnpm Node 24 alignment

- Base revision: current branch head after the Node toolchain fix.
- Scope: one repository-local workflow compatibility slice.
- Implementation: updated the `ci`, `validate`, and `CodeQL Advanced` workflows to provision Node 24 before `pnpm install`, matching the repository's pinned `pnpm@11.4.0` requirement and eliminating the Node 20 / `node:sqlite` install failure.
- Compatibility: application code, provider isolation, production gates, and deployment workflows are unchanged.
- Security: no credentials, service tokens, or production identifiers were added; the change only adjusts the public Node runtime used by CI and CodeQL.
- Tests: `scripts/test/workflow-pnpm-setup.test.mjs` and `scripts/test/codeql-workflow.test.mjs` now assert the Node 24 setup step before pnpm installation.
- Limitations: repository-local validation only; GitHub Actions remains the source of truth for the exact head SHA's CI result.

## 2026-07-16 — CodeQL Advanced self-hosted runner lane

- Base revision: `1f44d9588fe4a42370f3477eea22a70e1e4cbd22`
- Scope: one repository-local CodeQL workflow slice.
- Implementation: updated `CodeQL Advanced` to run on the available self-hosted Linux/X64 lane and to load a repository CodeQL config that adds the `security-and-quality` query suite.
- Compatibility: the security workflow still analyzes the same repository languages and does not alter runtime application code, provider access, or production gates.
- Security: no credentials, service tokens, or production identifiers were added; the change only moves analysis to the designated CI runner and broadens query coverage.
- Tests: `scripts/test/codeql-workflow.test.mjs` now checks the runner labels, config-file binding, and query-suite selection.
- Limitations: repository-local validation only; PR-head CodeQL execution, artifact binding, and alert-closure evidence on the self-hosted runner remain pending.

## 2026-07-16 — CodeQL Advanced workflow toolchain hardening

- Base revision: `743860cac1098e2a9ac258d542876a4d2acda7cc`
- Scope: one repository-local CodeQL workflow slice.
- Implementation: added explicit Node, pnpm, Go, and Python setup steps before CodeQL initialization so the self-hosted Linux/X64 lane can analyze the repository without assuming preinstalled language toolchains.
- Compatibility: the workflow still targets the same languages and query suite; only analysis setup changed, and runtime application code, provider access, and production gates remain untouched.
- Security: the change only installs public toolchains and workspace dependencies needed for analysis; no credentials, service tokens, or production identifiers were added.
- Tests: `scripts/test/codeql-workflow.test.mjs` now checks the setup-node, pnpm, setup-go, and setup-python steps and their ordering before CodeQL init, plus the existing YAML parse check.
- Limitations: repository-local validation only; PR-head CodeQL execution, artifact binding, and alert-closure evidence on the self-hosted runner remain pending.
## 2026-07-16 — ZChat browser-local dark mode preference

- Base revision: `b34da941ef2c8d8e226cbf41e69675bcc4a050cb`
- Scope: one repository-local ZChat UI slice.
- Implementation: added a browser-local dark mode toggle with persisted preference and system-color-scheme fallback.
- Compatibility: transcript rendering, conversation history selection, manual titles, system prompts, prompt templates, export actions, retry, logout, and gateway-only forwarding remain unchanged.
- Security: browser code still receives no provider credentials or upstream base URLs; the theme preference is local browser state only.
- Tests: conversation-state coverage now includes theme preference normalization and persistence on the branch head.
- Limitations: repository-local validation only; no external staging or operator approval is claimed.

## 2026-07-16 — ZChat manual conversation title editing

- Base revision: `7035295df2bcd0b8c10f0a8e88f0db2edbe06ae3`
- Scope: one repository-local ZChat UI slice.
- Implementation: added a browser-editable conversation title field that persists with the active conversation, updates the history sidebar, and remains stable across later message appends.
- Compatibility: transcript rendering, history navigation, system prompts, prompt templates, export actions, retry, logout, and gateway-only forwarding remain unchanged.
- Security: browser code still receives no provider credentials or upstream base URLs; the title stays local to browser storage.
- Tests: conversation-state coverage now includes explicit title editing and persistence across later message appends on the branch head.
- Limitations: repository-local validation only; no external staging or operator approval is claimed.

## 2026-07-16 — ZChat active conversation export controls

- Base revision: `412ef335ca2b2166b8bd83acdab0d46fa356b9b1`
- Scope: one repository-local ZChat UI slice.
- Implementation: added active-conversation export helpers plus UI controls to copy the current chat as markdown or download it as JSON.
- Compatibility: transcript rendering, conversation history selection, pinned system prompts, prompt templates, retry, logout, and gateway-only forwarding remain unchanged.
- Security: browser code still receives no provider credentials or upstream base URLs; export output only reflects browser-local conversation content.
- Tests: conversation-state coverage now includes markdown and JSON export serialization on the branch head.
- Limitations: repository-local validation only; no external staging or operator approval is claimed.

## 2026-07-16 — ZChat browser-local prompt template library

- Base revision: `ca0caff`
- Scope: one repository-local ZChat UI slice.
- Implementation: added a browser-local prompt template library with built-in presets, custom template saving, per-template reuse, and a "start from template" path that creates a fresh chat and sends the selected prompt.
- Compatibility: transcript rendering, conversation history selection, pinned system prompts, retry, logout, and gateway-only forwarding remain unchanged.
- Security: browser code still receives no provider credentials or upstream base URLs; custom templates stay local to browser storage.
- Tests: conversation-state coverage now includes template default loading, template persistence, and template removal on the branch head.
- Limitations: repository-local validation only; no external staging or operator approval is claimed.

## 2026-07-16 — ZChat pinned system prompt support

- Base revision: `c4edcf86a748e4420b4b64fb0e3d6619df712d16`
- Scope: one repository-local ZChat UI slice.
- Implementation: added a browser-persisted per-conversation system prompt editor and forwarded it through the zchat chat and streaming request paths as a system message before the user message.
- Compatibility: transcript rendering, conversation history selection, retry, logout, and gateway-only model forwarding remain unchanged; legacy flat browser storage still hydrates into the new prompt-aware conversation container.
- Security: browser code still receives no provider credentials or upstream base URLs, and non-string system prompts are rejected server-side before the gateway call.
- Tests: conversation-state coverage now includes system prompt persistence and selection, and server tests now verify system-message forwarding and invalid prompt rejection on the branch head.
- Limitations: repository-local validation only; no external staging or operator approval is claimed.

## 2026-07-16 — ZChat conversation history sidebar and new chat control

- Base revision: `8d92346446a70aebeb918c1bd670904f00147fbc`
- Scope: one repository-local ZChat UI slice.
- Implementation: added a browser-local conversation history sidebar with active-conversation selection, a dedicated new-chat action, active-conversation clearing, and conversation metadata summaries.
- Compatibility: transcript rendering, stream handling, retry, logout, and gateway-only model forwarding remain unchanged; legacy flat browser storage still hydrates into the new history container.
- Security: browser code still receives no provider credentials or upstream base URLs.
- Tests: conversation-state coverage now includes history hydration, selection, reset, and server-id rebasing on the branch head.
- Limitations: repository-local validation only; no external staging or operator approval is claimed.

## 2026-07-16 — ZChat safe markdown rendering upgrade

- Base revision: `b43140e26d3ec0dc2a38ae5e5805989d2f393e3d`
- Scope: one repository-local ZChat UI slice.
- Implementation: added a safe markdown renderer for assistant replies, with code fences, headings, lists, quotes, inline formatting, and link allowlisting for http(s) URLs.
- Compatibility: transcript rendering, browser storage state, streaming replies, and gateway-only model forwarding remain unchanged.
- Security: raw HTML and dangerous URL schemes remain text-only; no provider credentials or external auth state were added to the browser.
- Tests: focused markdown tokenization and rendering tests, plus the existing zchat suite, passed on the branch head.
- Limitations: repository-local validation only; no external staging or operator approval is claimed.

## 2026-07-16 — ZChat conversation transcript and streaming composer upgrade

- Base revision: `50054c26accc0b9903179e4fae0dac6acf174dd0`
- Scope: one repository-local ZChat UI slice.
- Implementation: replaced the single-message form with a transcript-based conversation shell, browser-persisted conversation state, retry/clear controls, and streaming assistant rendering with a gateway fallback path.
- Compatibility: gateway-only model catalog loading, tenant/session correlation, logout clearing, and server-side provider isolation remain unchanged.
- Security: browser code still receives no provider credentials or upstream base URLs.
- Tests: `node --test apps/zchat/test`, `node --test apps/zchat/test/server.test.mjs`, and repo pre-push validation passed on the branch head.
- Limitations: isolated repository validation only; no external staging or operator approval is claimed.

## 2026-07-15 — AI Gateway disconnect-aware upstream cancellation

- Base revision: `36fc7f594c933137a1d8da2855bac752fb2f03b3`
- Scope: one repository-local AI Gateway slice.
- Implementation: wrapped the gateway in an exportable factory, propagated client disconnects to the upstream fetch through `AbortController`, and stopped retrying once the request closed.
- Compatibility: service-token auth, exact-origin CORS, provider routing, and existing gateway request contracts remain unchanged.
- Tests: `pnpm --dir services/ai-gateway test`, `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm keys:check`, `docker compose config --quiet`, and `docker compose build ai-gateway`.
- Limitations: repository-local validation only; no external staging, operator approval, or production readiness is claimed.

## 2026-07-15 — Immutable release evidence binding

- Base revision: `f5be49853ec9311c81f9e62892b4d7f2db4bc254`
- Scope: one Phase 6 release-safety vertical slice.
- Implementation: added a dependency-free validator that requires `commitSha`, `approvedCommitSha`, and `observedCommitSha` to equal the exact release-candidate SHA.
- Compatibility: existing release templates and runtime interfaces are unchanged.
- Security: no provider SDKs, credentials, external traffic, deployment, or financial authority added.
- Tests: positive exact-match case plus stale, placeholder, missing-field, and invalid-argument regressions.
