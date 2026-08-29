# Z.A.R.V.I.S. Feature Matrix

Epic: #148

| Capability | Status | Evidence | Security boundary |
|---|---|---|---|
| Typed text command | Implemented | `apps/zarvis-console/public/app.js` | Same-origin owner-only JSON proxy |
| Browser push-to-start transcript | Implemented | `apps/zarvis-console/public/app.js` | No continuous listening |
| Realtime ZVoice transcript bridge | Implemented | `apps/zvoice/server.mjs`, `apps/zvoice/public/app.js` | Fixed owner identity; no provider secret in browser |
| Intent routing for GitHub repository status | Implemented | `services/zarvis-orchestrator/src/contracts.mjs` | Deterministic constrained parser |
| Read-only GitHub status tool | Implemented | `services/zarvis-orchestrator/src/github-status-tool.mjs` | GET-only fixed host; no redirects |
| Speech-ready Thai/English response | Implemented | `services/zarvis-orchestrator/src/orchestrator.mjs` | Generated from normalized fields |
| Browser speech output | Implemented | Console and ZVoice browser clients | Browser speech synthesis |
| Tool audit event | Implemented | `zarvis.audit.tool-executed.v1` | Allowlisted fields; no secrets |
| Append-only session transcript/events | Implemented | `zarvis.session.event.v1`, `FileSessionStore` | Fixed-path journals; mode 0600 files |
| Command idempotency | Implemented for read-only tools | `command_id` fingerprint/result envelope | Identical replay; conflicting reuse returns 409 |
| Session history view/delete | Implemented | `GET/DELETE /v1/sessions/{id}` | Owner service auth; deletion confirmation required |
| Durable multi-step task state | Implemented for read-only DAG | `services/zarvis-task-gateway`, durable agent adapters | Fixed owner; fixed-path job/queue/audit files |
| Exact-plan owner approval | Implemented for task plans | `zarvis.task.approval.v1`, SHA-256 digest + nonce | Single-use, 15-minute expiry, worker recheck |
| Pause/resume/cancel/retry | Implemented for task lifecycle | `ZarvisTaskRuntime` | Approved/pending pause only; retry limit enforced |
| Step checkpoints and dependency order | Implemented | `ZarvisPlanWorkerRuntime` | Earlier-step dependency rule; read-only registry |
| Owner-confirmed memory writes | Implemented | `services/zarvis-memory`, `zarvis.memory.proposal.v1` | Proposal has no effect until exact digest+nonce confirmation |
| Working/episodic/semantic/procedural memory | Implemented | `ZarvisMemoryRuntime` | Classification-specific retention limits |
| Encrypted memory at rest | Implemented | `EncryptedMemoryStore` | AES-256-GCM; external 32-byte master key; fixed journal path |
| Memory provenance and retrieval | Implemented | Memory snapshot schemas and lexical retriever | Owner-scoped, provenance returned, no persisted plaintext index |
| Memory correction/export/delete | Implemented | Privacy console and memory APIs | Versioned correction; owner export; journal compaction deletion |
| Secret-safe memory policy | Implemented | `assertMemorySafe` and tests | Raw credentials, private keys, tokens, and card-like data rejected |
| Memory retention purge | Implemented | Authenticated memory worker | Expired hidden immediately and physically compacted |
| Explicit multimodal consent | Implemented | `services/zarvis-perception` | Purpose/modality digest, nonce, expiry, stop/delete |
| One-shot file/screen/camera perception | Implemented | Perception console and runtime | Immediate media-track stop; no continuous capture |
| Raw-media retention | Blocked | Perception encrypted journal | Only redacted analysis and provenance persist |
| Prompt-injection isolation for media | Implemented | Perception security result | Untrusted content cannot alter policy or grants |
| Reversible local mutation | Implemented for one fixture | `services/zarvis-action-gateway` | Only `sandbox.preference.set`; no external side effect |
| Dry-run action impact preview | Implemented | `zarvis.action.preview.v1` | Binds previous/next value, owner, scope, and expiry |
| Exact local action approval | Implemented | `zarvis.action.approval.v1` | SHA-256 digest plus one-time nonce |
| Isolated action worker | Implemented | Action `worker.mjs`, internal queue API | Worker has no owner token and sees only approved IDs |
| Action rollback | Implemented | `zarvis.action.rollback.v1` | Execution-bound proof and compare-and-set restoration |
| Emergency action stop | Implemented | Action runtime and owner console | Persist stop first; revoke pending/approved actions |
| Owner-defined local schedules | Implemented | `services/zarvis-proactive` | Only allowlisted read-only local health checks |
| Quiet hours and notification budgets | Implemented | `zarvis.proactive.policy.v1` | Enforced server-side in owner timezone |
| Confidence, cooldown, and deduplication | Implemented | Proactive runtime and tests | Suppression reasons remain audited and visible |
| Missed-run and restart recovery | Implemented | Durable subscription snapshots | Skip or run-once policy; fixed event journal |
| Explainable suggestion inbox | Implemented | Proactive console and notification schema | Source, evidence, confidence, and decision exposed |
| Suggestion feedback and revocation | Implemented | Feedback schema and owner APIs | Useful/irrelevant/false-positive; immediate schedule revoke |
| Proactive action handoff | Implemented without execution | `zarvis.proactive.action-handoff.v1` | Always requires owner approval and fixes `executed: false` |
| Autonomous proactive mutation | Blocked | No action credential or execution client | Scheduler cannot approve or execute actions |
| Local Ubuntu/Linux deployment | Implemented | `compose.zarvis-local.yml`, setup script | Loopback bind, host network, dropped capabilities, read-only root |
| Container resource controls | Implemented | Hardened Compose and container evidence | CPU, memory, PID, file-descriptor, tmpfs, capability limits |
| Bounded local SLO | Implemented as release gate | `zarvis-local-release-acceptance.mjs` | Zero errors and p95 ≤ 750 ms for bounded health/status sample |
| Security red-team | Implemented as release gate | `zarvis-local-red-team.mjs` | Auth, capability, path, size, SSRF, secret, non-mutation checks |
| Restart/worker interruption recovery | Implemented as release gate | `zarvis-local-restart-drill.mjs` | Durable state retained; recovery objective ≤ 60 seconds |
| Backup and restore | Implemented as release gate | backup/restore/verification scripts | SHA-256 archives; secrets excluded; restored IDs verified |
| Independent credential rotation | Implemented as release gate | `zarvis-local-verify-rotation.mjs` | Old credentials rejected; new scoped credentials accepted |
| Immutable release manifest | Implemented | `zarvis-local-build-manifest.mjs` | SHA-256 evidence inventory, release SHA, assertions, no secrets |
| Main-branch evidence provenance | Implemented | `ZARVIS Local Release` workflow | Manifest attestation on non-PR runs |
| Arbitrary shell/browser/device control | Blocked | Default-deny action registry | Requires a new narrowly scoped reviewed capability |
| Automated local production evidence | Complete after release workflow passes | Issue #156 and release artifact | CI proves ephemeral Ubuntu local deployment and drills |
| Actual owner-host acceptance | Pending actual target host | `docs/releases/zarvis-local-owner-acceptance.md` | CI cannot prove physical host/browser/device configuration |
