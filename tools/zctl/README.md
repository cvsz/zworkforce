# zctl

`zctl` is the guarded Docker Compose lifecycle, source-control, and release-transition CLI for `z-platform`.

Implemented commands:

- `start`, including `--service`, `--build`, and `--wait`
- `stop`, preserving data by default
- `restart`, including `--recreate` and `--wait`
- `build`, including `--service`, `--no-cache`, `--pull`, `--push`, and SBOM generation
- `update`, using fetch plus fast-forward-only merge
- `upgrade`, using checksum-bound plan/apply and explicit rollback
- `status`, `health`, `logs`, `doctor`, and `version`

Safety controls:

- operation locking under `.zctl/operation.lock`
- mode-0600 JSON audit records under `.zctl/audit`
- checksum-bound upgrade plans under `.zctl/plans`
- release and rollback evidence under `.zctl/releases`
- service allow-list validation through `docker compose config --services`
- dirty-tree rejection for build, update, and upgrade planning
- immutable target resolution with `git rev-parse --verify <ref>^{commit}`
- no reset, clean, rebase, or force-push operations
- staging and production reject local image builds and destructive purge
- production apply/rollback requires `--confirm-environment production`
- OCI revision, source, created, and version labels on service images
- SPDX JSON SBOM output under `.zctl/sbom`

Build and test:

```bash
cd tools/zctl
go test ./...
go vet ./...
go build -o ../../bin/zctl ./cmd/zctl
```

Examples:

```bash
bin/zctl doctor
bin/zctl start --profile local --wait
bin/zctl build --service ai-gateway --pull
bin/zctl update --branch main --restart

# Create a checksum-bound immutable plan
bin/zctl upgrade --profile local --to v1.3.0 --plan

# Apply exactly that plan
bin/zctl upgrade --profile local --apply --plan-id <plan-id>

# Explicit rollback to the plan's previous revision
bin/zctl upgrade --profile local --rollback --plan-id <plan-id>

# Production requires explicit environment confirmation
bin/zctl upgrade --profile production --apply --plan-id <plan-id> \
  --confirm-environment production
```

## Governed upgrade sequence

Planning performs:

```text
verify clean tree
→ resolve current and target immutable commits
→ inspect Compose image references
→ discover backup/migration/rollback hooks
→ calculate plan checksum
→ write mode-0600 plan evidence
```

Apply performs:

```text
acquire exclusive operation lock
→ validate plan ID, checksum, profile, and current revision
→ require production environment confirmation
→ execute backup hook
→ switch to exact target commit
→ pull images
→ execute pre-migration hook
→ deploy
→ execute migration hook
→ verify health
→ write release evidence
```

A deployment, migration, or health failure triggers rollback to the exact `beforeRevision`, invokes the rollback hook when configured, redeploys, verifies health, and records `ROLLED_BACK` or `RELEASE_FAILED` evidence.

Optional executable hooks:

```text
scripts/zctl/backup
scripts/zctl/pre-migrate
scripts/zctl/migrate
scripts/zctl/rollback
```

Each hook is invoked directly without `sh -c` and receives:

```text
--plan-id <id> --before <sha> --target <sha> --profile <profile>
```

Staging and production plans require `scripts/zctl/backup`. Hooks must be executable and must not print secrets. Migration rollback remains application-specific; operators must ensure the rollback hook is compatible with each schema transition.
