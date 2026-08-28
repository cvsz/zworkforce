# Migration Source Inventory

Source repository: `cvsz/zeaz-platform`

## Adopted sources

| Source | Reusable evidence | Z Platform destination | Decision |
|---|---|---|---|
| `reports/platform/apps-stack-inventory.md` | App stacks, ports and domains | Architecture and migration planning | Use only as inventory; do not copy legacy port allocation |
| `reports/platform/apps-source-review.md` | Source size, ownership and duplication signals | Migration triage | Use to select small, independently testable components |
| `apps/zaicoder/README.md` and backend docs | CLI/web split, testing and provider boundaries | `apps/zaicoder` | Migrate through gateway-backed modules only |
| `apps/zai-factory/skills-vault` | Generator and migration playbooks | `tools/zai-factory` | Import only audited templates/manifests |
| `apps/zow/scripts/migration/README.md` | Incremental, reversible desktop migration process | `apps/zow` | Reuse rollback-first migration discipline; do not copy vendor release URLs |
| `apps/zwallet/CODEX_TASKS.md` | Contract-first, idempotency, security and test gates | `services/billing-ledger` | Reuse policy only; never import wallet signing or payment secrets |
| `apps/zai-stack` skills and orchestration docs | Agent-role and policy concepts | `services/agent-orchestrator` | Extract contracts and approval policy before worker runtime |

## Exclusions

The new platform does not inherit legacy production hostnames, port assignments, provider keys, wallet secrets, payment credentials, tunnel configuration, or deployment identifiers.

## Import gate

Every source import must record:

1. Exact source path and commit.
2. License status.
3. Dependency and secret scan results.
4. Tests and rollback path.
5. Target owner and platform contract version.
