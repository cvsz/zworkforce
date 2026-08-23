# zWorkforce Skywork-Inspired Workspace Upgrade Execution Plan

**Updated:** 2026-08-17  
**Status:** active implementation plan  
**Scope:** workspace UX, conversations/context, artifacts/review, skill lifecycle, sandbox/worktrees, browser automation, notifications, web-product flows and FinOps  
**References:** `docs/SKYWORK-CHANGELOG-REVERSE-ENGINEERING.md`, official Skywork Help changelog surfaces, and the official Skywork Desktop changelog

## 1. Mission

Adopt the strongest publicly documented Skywork workspace-agent product patterns where they improve zWorkforce, without copying proprietary code or weakening zWorkforce security and governance.

The target is not a clone. The target is a stronger zWorkforce operator/workspace experience built on existing durable tasks, workflows, artifacts, memory, approvals, MCP, Z.A.R.V.I.S., Zider, Zeto and FinOps.

## 2. Definition of complete

The upgrade is complete only when all applicable criteria pass:

- project/conversation state is durable and tenant scoped;
- context status and compaction are explicit and auditable;
- artifacts and subagent/tool execution are reviewable from durable evidence;
- local workspace access is sandboxed, allowlisted and bounded;
- git worktree/branch operations are isolated and reviewable;
- browser mutations remain explicit approval-gated actions;
- skill install/update/enable/disable/rollback obey policy and preserve prior versions;
- repeated workflows produce reviewable candidates, never silently activated production skills;
- notifications are tenant scoped and connector delivery is opt-in/policy controlled;
- FinOps preflight and actual usage are backed by durable ledger data;
- social publishing continues through durable approval/outbox/provider boundaries;
- design guidelines are versioned, attributable and enforced by generation/QA policy rather than UI hints only;
- memory imports are previewable, provenance-preserving, consent-based and tenant scoped;
- tests cover auth, tenancy, traversal, SSRF, skill authority expansion, idempotency, cancellation, retry and rollback;
- required CI/security/package/Windows/release gates are green on the exact candidate SHA.

## 3. Delivery phases

### Phase SW0 — Capability mapping and lifecycle foundation

**Status:** IMPLEMENTED FOUNDATION / PR VALIDATION IN PROGRESS

Deliverables:

- `docs/SKYWORK-CHANGELOG-REVERSE-ENGINEERING.md` with chronological public feature mapping.
- `ROADMAPS.md` and master execution plan references.
- governed skill lifecycle in Z.A.R.V.I.S. runtime:
  - immediate active resolution after installation;
  - enable/disable;
  - active semantic version selection;
  - safe system-skill automatic update;
  - explicit rollback;
  - no silent tool-capability expansion;
  - no read→write escalation;
  - no approval weakening.
- orchestrator execution must resolve only enabled skill versions; lifecycle state is not presentation-only.

Primary implementation:

- `packages/zarvis/services/zarvis-orchestrator/src/skill-catalog.mjs`
- `packages/zarvis/services/zarvis-orchestrator/src/orchestrator.mjs`
- `packages/zarvis/services/zarvis-orchestrator/test/skill-catalog.test.mjs`
- `packages/zarvis/services/zarvis-orchestrator/test/orchestrator-skill-execution.test.mjs`

Exit criteria:

- existing catalog behavior remains compatible;
- lifecycle tests pass;
- disabled versions cannot execute;
- auto-update fails closed on authority expansion;
- prior versions remain resolvable for rollback;
- affected Z.A.R.V.I.S., root CI, CodeQL and dependency gates pass.

### Phase SW1 — Durable projects and conversations

Use the repository's existing database composition instead of introducing a parallel store. The current data layer is `Database = AutomationMixin + TaskMixin + FinOpsMixin + GovernanceMixin + MigrationMixin + DatabaseBase`, with schemas split across `db_schema.py`, `db_schema_v3.py` and version-specific initialization in `db_base.py`.

Planned files:

- `zworkforce/db_schema_workspace.py` — additive workspace schema kept separate from legacy/v3 schema blocks.
- `zworkforce/db_workspace.py` — `WorkspaceMixin` with tenant-scoped project/conversation/message operations.
- `zworkforce/db_base.py` — import/initialize workspace schema and advance schema version only with migration/test updates.
- `zworkforce/db.py` — compose `WorkspaceMixin` into the canonical `Database` class.
- `zworkforce/api.py` — authenticated workspace endpoints.
- `tests/test_workspace.py` — SQLite/data-layer contract.
- `tests/test_workspace_api.py` — API/RBAC/tenant contract.
- `tests/test_v3_postgres.py` — PostgreSQL workspace schema/round-trip evidence when this slice lands.

Repository-backed entities:

```text
workspace_projects
workspace_conversations
workspace_messages
```

Future SW2 entities may add:

```text
workspace_context_snapshots
workspace_context_members
```

Use fields on project/conversation rows for pin/archive state instead of creating a redundant pin table unless multi-user pins become a requirement.

Required fields include tenant ID, owner/actor, project ID, timestamps, status, title, source task/workflow references and retention policy. Foreign keys involving project/conversation ownership should include `tenant_id` so cross-tenant attachment is rejected structurally as well as by repository queries.

Initial APIs:

```text
POST   /api/v1/workspaces/projects
GET    /api/v1/workspaces/projects
GET    /api/v1/workspaces/projects/{id}
POST   /api/v1/workspaces/projects/{id}/rename
POST   /api/v1/workspaces/projects/{id}/pin
POST   /api/v1/workspaces/projects/{id}/archive
POST   /api/v1/workspaces/conversations
GET    /api/v1/workspaces/conversations/{id}
GET    /api/v1/workspaces/conversations?query=&project_id=&status=
POST   /api/v1/workspaces/conversations/{id}/rename
POST   /api/v1/workspaces/conversations/{id}/pin
POST   /api/v1/workspaces/conversations/{id}/archive
POST   /api/v1/workspaces/conversations/{id}/messages
GET    /api/v1/workspaces/conversations/{id}/messages
DELETE /api/v1/workspaces/conversations/{id}
```

The current HTTP server primarily exposes GET/POST actions. Prefer explicit action endpoints for rename/pin/archive rather than adding PATCH solely for cosmetic REST symmetry.

Security:

- every query is tenant scoped;
- composite tenant ownership is enforced for project→conversation→message relationships;
- conversation IDs are opaque and cannot switch tenant ownership;
- creation happens only after authentication/authorization;
- reads require `workspace:read`; mutations require `workspace:write`; destructive deletion may use `workspace:delete`/admin policy;
- deletion/forget is audited and retention-aware;
- message/artifact references are bounded and validated; raw host paths are not accepted.

Tests:

- cross-tenant read/write negative tests;
- cross-tenant project attachment rejected;
- pin/archive/search persistence;
- message ordering and restart safety;
- title/autoname validation;
- deletion/cascade and retention semantics;
- SQLite and PostgreSQL round trips;
- API scope enforcement and audit evidence.

### Phase SW2 — Context budget, compaction and dynamic prompt caching

Add explicit context accounting and prompt caching per conversation:

- estimated/actual token budget;
- model-specific context ceiling;
- OpenRouter dynamic prompt cache blocks (`cache_control`) for static instructions, tool definitions, and long documents;
- dynamic parameter injection (`nextTurnParams`) for context-aware skill loading;
- included message/artifact/memory references;
- compaction threshold and reason;
- compaction artifact hash/version.

`/compact` creates a new attributable summary artifact and context snapshot. It does not overwrite durable conversation history or automatically write long-term memory.

Tests:

- deterministic snapshot membership;
- no cross-tenant memory inclusion;
- prompt cache hit-rate verification;
- compaction rollback/read-old-context;
- oversized attachment handling;
- sensitive-data redaction hooks.

### Phase SW3 — Slash command, ACP and task-composer registry

Commands:

```text
/plan
/review
/compact
/undo
/goal
/status
/artifacts
/cost
/skill
/workflow
/feedback
```

Implementation rules:

- parser is presentation-independent;
- server resolves command authorization and capabilities;
- `/undo` invokes the pre-mutation file snapshot rollback engine with visual diff preview;
- bidirectional Agent Client Protocol (ACP) JSON-RPC bridge enabled for IDE/CLI sessions;
- commands cannot bypass normal API/RBAC/policy checks;
- attachment references are artifact IDs, not arbitrary host paths;
- unknown commands fail safely with discoverable help.

### Phase SW4 — Task summary, artifact manifest, doom-loop detection, safety hooks and execution sidecar (Free Model First)

For every task/workflow run expose:

- summary and intent classification;
- Free Model First priority (`openrouter/free`, `qwen-2.5-coder-32b:free`, `deepseek-r1:free`);
- pre-mutation file snapshot checksums and rollback points;
- Doom-Loop detection: automated detection and mitigation of repeated identical tool arguments or cyclical errors;
- deterministic safety hooks (`branch-guard`, `secret-guard`, `destructive-guard`, `auto-approve-readonly`);
- LLM wiki pattern for compounding project memory and pre-mortem execution reviews;
- Advisor/Subagent tool integration: compact uncertainty validation and delegate task spawning;
- artifact manifest and changed files;
- tool execution timeline with sanitized parameters;
- subagent lineage and active execution mode;
- approval state (HITL gates) and execution ceilings;
- cost/latency/model route telemetry;
- next recommended actions.

The UI can render main chat + review + file preview + side discussion without duplicating authoritative execution state.

### Phase SW5 — Scoped local workspace sandbox

**Status:** SW5A durable workspace grants and SW5B process enforcement IMPLEMENTED on `main` (PRs #96, #97, #98)

SW5A merged as PR #96 (`workspace_grants6` schema, `WorkspaceGrantService`, admin `workspace:grant` API, re-resolved roots on every use). SW5B merged as PR #97 (durable grant enforcement on local file tools) and PR #98 (probed production process containment): command membership and argument-array execution (no `shell=True`), cwd and environment sanitization, memory/process/open-file/fsize/cpu bounds via `prlimit`, network policy `deny`, timeouts, output caps and fail-closed sandbox availability probing. `network_policy=allowlisted` remains explicitly unimplemented and is refused at runtime. External sandbox/runtime drills remain operator-owned `external evidence` per `docs/PRODUCTION-EVIDENCE.md`.

New workspace grant contract:

```json
{
  "tenant_id": "...",
  "workspace_id": "...",
  "root": "operator-approved canonical path",
  "read": true,
  "write": false,
  "commands": ["git", "python", "npm"],
  "network_policy": "deny|allowlisted",
  "expires_at": "ISO-8601"
}
```

Requirements:

- canonicalize before authorization;
- block `..`, symlink/junction escape and device paths;
- subprocesses use argument arrays, no `shell=True`;
- time/memory/output/process limits;
- sanitized environment;
- write/command mutation requires policy/approval as configured;
- audit start/end/exit code without leaking secrets.

### Phase SW6 — Git branch/worktree isolation

Provide an adapter over approved repositories:

- create named feature worktree;
- inspect diff/status;
- run allowlisted checks;
- commit only with explicit mutation authorization;
- open PR through GitHub boundary;
- cleanup expired worktrees safely.

Never allow a task to rewrite protected/default branches directly.

### Phase SW7 — Zider browser-use contract

Browser tools are split into classes:

**Read-only:** navigate, inspect DOM/text, screenshot, extract structured fields.

**Mutating:** click action controls, submit forms, uploads, purchases, account settings, send/publish actions.

Mutating tools require explicit declared intent plus approval/policy where configured. Add domain/URL allowlists, SSRF protections, timeout/cancel, dedupe for external side effects, evidence screenshots/receipts where appropriate and secret-safe logging.

### Phase SW8 — Skill marketplace, discovery and reusable workflow compiler

Build on Phase SW0:

- signed remote skill package install using existing registry trust controls;
- source metadata and publisher/signature evidence;
- immediate activation only inside existing capability envelope;
- safe automatic updates for approved `system` skills;
- manual review for capability expansion;
- discovery score based on task intent, domain, capability fit, outcome quality, latency and cost;
- repeated-workflow detector creates a draft workflow/skill candidate;
- generated candidates require schema validation, policy review and tests before enablement.

### Phase SW8A — Skywork Web changelog integrations

The current Skywork Help landing page exposes three recent web-product changes that map cleanly onto existing zWorkforce subsystems. Treat them as capability references, not implementation dependencies.

#### Social Publishing Flow → Zeto

- extend Zeto's existing content lifecycle rather than create a second publisher;
- composition/approval/scheduling/publish remains `draft → review → approved → scheduled → publishing → live|failed`;
- use existing durable queue/outbox, provider adapters, idempotency keys, audit trail and retry/dead-letter semantics;
- provide social-format templates and platform previews as presentation features only; provider side effects still go through approval/policy.

#### Design Guidelines in Knowledge Base → Brand/Design policy

- store design guideline documents as versioned tenant artifacts/knowledge records with owner, source, hash and effective version;
- project/brand contexts reference guideline versions explicitly;
- generation tools receive derived non-secret design constraints;
- Zeto QA/brand-safety evaluates outputs against the active guideline version;
- zsp-aitool/Zider can preview guidelines but cannot silently modify active production policy.

#### SkyClaw memory import → portable zWorkforce memory import

- add import adapters for operator-supplied AI memory/export files rather than scraping private accounts;
- support preview/dry-run, source/provider label, import batch ID, hash/dedupe, conflict handling and explicit commit;
- imported memory is tenant scoped and records provenance, actor, timestamp and source artifact hash;
- do not treat imported model instructions as trusted system policy;
- redact/reject secrets and unsupported sensitive fields according to tenant policy;
- allow batch rollback/delete through the recorded import batch where retention rules permit.

### Phase SW9 — Notification center and proactive delivery

Durable notifications:

```text
task_completed
approval_required
question_required
task_failed
budget_risk
scheduled_run_completed
agent_stalled
security_policy_denied
```

Support in-app first. External IM/email/connector delivery remains opt-in and uses approved connector boundaries.

### Phase SW10 — FinOps preflight and detailed ledger

Before expensive work:

- estimate model/tool/artifact cost range;
- compare with tenant/task budget;
- warn or deny according to policy;
- record actual provider/model/tool cost events;
- expose chargeback/showback drilldown by tenant/project/task/agent/model.

Do not invent credit balances. Subscription/purchase integration is a separate payment-provider boundary and must not be embedded into agent runtime authorization.

### Phase SW11 — Operator UX parity

Web and Windows surfaces:

- project/conversation navigation;
- pin/archive/search;
- task quick start;
- next-step suggestions;
- context gauge + compact control;
- review/artifact/subagent sidecar;
- Markdown source/rendered toggle;
- safe HTML preview sandbox;
- theme profiles;
- notification center;
- skill manager and version rollback;
- cost/budget panel.

Accessibility requirements include keyboard navigation, screen reader labels, high contrast, reduced motion and non-color status indicators.

### Phase SW12 — Hardening and release evidence

Required suites:

- Python unit/integration/PostgreSQL;
- Node/Z.A.R.V.I.S. package tests;
- Zider extension/server tests;
- Windows build/test/package;
- sandbox path/symlink escape tests;
- command allowlist and cancellation tests;
- browser mutation approval tests;
- skill authority-expansion tests;
- context/tenant negative tests;
- social publish idempotency/provider-fake tests;
- design guideline version/tenant enforcement tests;
- memory import provenance/dedupe/rollback tests;
- CodeQL, dependency review, SBOM/provenance;
- staging E2E for workspace → plan → execute → review → approve → artifact → PR/publish.

## 4. PR sequence

1. `feat/skywork-inspired-workspace-upgrade` — research map, plans and governed skill lifecycle foundation.
2. `feat/workspace-project-conversations` — additive workspace schema/mixin + durable project/conversation/message API.
3. `feat/workspace-context-commands` — context budget/compaction + slash command registry.
4. `feat/workspace-task-sidecar` — summaries, artifacts, subagent/tool trace projection.
5. `feat/workspace-local-sandbox` — scoped local workspace executor.
6. `feat/workspace-git-worktrees` — branch/worktree adapter and diff/PR workflow.
7. `feat/zider-browser-use-contract` — read/mutate browser tool boundary.
8. `feat/skill-marketplace-reusable-workflows` — signed install/discovery/candidate compiler.
9. `feat/zeto-design-memory-portability` — social publishing UX alignment, design guideline policy, memory import batches.
10. `feat/workspace-notifications-finops` — notification center + cost preflight/ledger UX.
11. `feat/workspace-ux-hardening` — Web/WinUI parity, accessibility, E2E and release evidence.

## 5. Validation baseline

```bash
python3 -m compileall -q zworkforce tests scripts
PYTHONPATH=. python3 -m unittest discover -s tests -v
zworkforce doctor
pnpm --dir packages/zarvis install --frozen-lockfile
pnpm --dir packages/zarvis peers check
pnpm --dir packages/zarvis test
pnpm --dir packages/zarvis audit --audit-level high
python3 scripts/verify_release.py --expected 3.0.3
```

Changed packages must also execute their package-native type/build/test/security gates. PostgreSQL behavior changes must run the real CI PostgreSQL service tests. Production claims remain subject to `docs/PRODUCTION-EVIDENCE.md`.