# Upgrade source inventory

This inventory records behavioral references for ZeaZ Provider upgrades.
Sources are pinned to inspected commits. No source code is automatically
copied, merged, executed, or installed from these repositories.

| Repository | Inspected commit | Use as reference | Exclude or redesign |
|---|---|---|---|
| `cvsz/aicoder` | `e5504ab` | Anthropic Messages, Files, Batch, citations, caching, thinking, tools and managed-agent API coverage | Shell execution, generated-code `exec`, hard-coded prices and model catalogs |
| `cvsz/zai-coder` | `e8a0cfb` | Command parsing, allowlists, workspace guards, approvals, audit events and checkpoints | Generated report sprawl, mock CI gates and bundled Open WebUI source |
| `cvsz/zcodex` | `318727c` | Deterministic installer phases, dry-run, runtime ownership, state, manifest, backup, doctor and reproducible releases | Codex-specific Node/npm mutation and Ubuntu-version assumptions |
| `cvsz/zc` | `dc50c62` | FastAPI lifecycle, readiness, normalized provider responses and server-side credentials | Corrupted `.zc/agents` rebranding, tracked virtualenv and legacy compatibility debt |
| `cvsz/z-platform` | `547caf2` | Provider allowlists, service-token boundary, local/free model catalog, rate limits, hardened Compose and migration policy | Financial services, unrelated applications and automatic bulk migration |

## Upgrade acceptance policy

Every imported behavior requires:

1. a written public contract or independently observable behavior;
2. a clean-room implementation in ZeaZ Provider;
3. unit and failure-path tests;
4. security and secret-boundary review;
5. documentation and rollback notes;
6. a source commit recorded in this inventory.

Repository availability or a matching filename is not permission to copy code.
Third-party license and provider terms must be reviewed for every dependency.

## Prioritized roadmap

### P0

- Cross-protocol streaming translation for Messages, Chat Completions and Responses.
- Provider health and model availability probes.
- Tenant-scoped client keys, rate limits and model allowlists.
- Signed release manifests in addition to SHA-256 verification.
- Update rollback command and doctor diagnostics bundle.

### P1

- Files, vision, citations and structured-output contract normalization.
- Usage and cost events without logging prompts or credentials.
- Local catalog for Ollama, vLLM, TGI and Hugging Face open-weight models.
- Circuit breakers and per-provider concurrency limits.
- Admin API for route status without exposing upstream keys.

### P2

- MCP tool gateway with explicit approvals.
- Isolated execution workers; no model-generated code in the API process.
- Durable audit storage and OpenTelemetry export.
- Policy-driven cloud fallback based on data classification.
