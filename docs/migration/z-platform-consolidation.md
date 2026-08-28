# z-platform → zworkforce Consolidation Plan

## Goal

Consolidate the `z-platform` monorepo into `zworkforce` to create a single unified codebase for all services, apps, and infrastructure.

## Current State

| Aspect | z-platform | zworkforce |
|--------|-----------|------------|
| Location | `/home/cvsz/z-platform/` | `/home/cvsz/platforms/zworkforce/` |
| Services | 15+ Node.js services | Python API/worker (Flask/FastAPI) |
| Apps | 11 frontend apps | Product packages (zarvis, zeto, zider, zsp-aitool) |
| Packages | `contracts` only | Full product suites |
| Infrastructure | K8s, Cilium, ArgoCD, Terraform | Docker Compose, K8s |
| Language | Node.js/TypeScript | Python + Node.js packages |

## Namespace Mapping

### Services → `services/` (new top-level in zworkforce)

| z-platform service | zworkforce target | Notes |
|--------------------|-------------------|-------|
| `ai-gateway` | `services/ai-gateway` | AI provider access layer |
| `agent-orchestrator` | `services/agent-orchestrator` | Durable jobs/queue |
| `agent-provider` | `services/agent-provider` | State backend for jobs |
| `workspace-runtime` | `services/workspace-runtime` | Sandbox execution |
| `billing-ledger` | `services/billing-ledger` | Usage/credits/invoices |
| `voice-gateway` | `services/voice-gateway` | WebSocket voice sessions |
| `voice-agent` | `services/voice-agent` | Speech pipeline |
| `zarvis-action-gateway` | `services/zarvis-action-gateway` | Local agent actions |
| `zarvis-proactive` | `services/zarvis-proactive` | Proactive agent |
| `zarvis-orchestrator` | `services/zarvis-orchestrator` | Zarvis orchestration |
| `zarvis-memory` | `services/zarvis-memory` | Agent memory |
| `zarvis-perception` | `services/zarvis-perception` | Perception layer |
| `zarvis-task-gateway` | `services/zarvis-task-gateway` | Task routing |
| `zarvis-owner-voice-edge` | `services/zarvis-owner-voice-edge` | Voice edge |
| `phase6-api` | `services/phase6-api` | Staging verification |
| `zc` | `services/zc` | ZC API/CLI/webapp |
| `z-prov` | `services/z-provisioning` | Service provisioning |

### Apps → `apps/` (new top-level in zworkforce)

| z-platform app | zworkforce target |
|----------------|-------------------|
| `agent-control-panel` | `apps/agent-control-panel` |
| `frontend` | `apps/frontend` |
| `zaicoder` | `apps/zaicoder` |
| `zarvis-console` | `apps/zarvis-console` |
| `zarvis-windows` | `apps/zarvis-windows` |
| `zchat` | `apps/zchat` |
| `zeaz-web` | `apps/zeaz-web` |
| `zow` | `apps/zow` |
| `zvoice` | `apps/zvoice` |
| `zwallet` | `apps/zwallet` |

### Packages → merge into existing `packages/`

| z-platform package | action |
|--------------------|--------|
| `contracts` | Move to `packages/contracts` (new) |

### Infrastructure → merge into existing `infrastructure/`

| z-platform infra | action |
|------------------|--------|
| `infrastructure/` (K8s, Cilium, ArgoCD, Terraform) | Merge into `infrastructure/` |

### Shared tooling

| z-platform path | action |
|-----------------|--------|
| `scripts/` | Merge into `scripts/` |
| `tools/` | Merge into `tools/` |
| `deploy/` | Merge into `deploy/` |
| `schemas/` | Merge into `schemas/` |
| `automation/` | Merge into `automation/` |
| `docs/` | Merge into `docs/` |

## Execution Steps

### Phase 1: Prepare zworkforce

1. Create new top-level directories: `services/`, `apps/`
2. Update `pnpm-workspace.yaml` to include `services/*` and `apps/*`
3. Update `package.json` workspaces field
4. Add `.gitattributes` merge strategy for conflicting files

### Phase 2: Move services

```bash
# From z-platform root
cd /home/cvsz/z-platform
for svc in services/*/; do
  dirname=$(basename "$svc")
  git mv "services/$dirname" "/home/cvsz/platforms/zworkforce/services/$dirname"
done
```

### Phase 3: Move apps

```bash
for app in apps/*/; do
  dirname=$(basename "$app")
  git mv "apps/$dirname" "/home/cvsz/platforms/zworkforce/apps/$dirname"
done
```

### Phase 4: Move packages

```bash
git mv packages/contracts /home/cvsz/platforms/zworkforce/packages/contracts
```

### Phase 5: Merge infrastructure

```bash
# Merge K8s manifests
cp -r infrastructure/kubernetes/* /home/cvsz/platforms/zworkforce/infrastructure/kubernetes/
# Merge Terraform
cp -r infrastructure/terraform/* /home/cvsz/platforms/zworkforce/infrastructure/terraform/
# Merge Cilium policies
cp -r infrastructure/cilium/* /home/cvsz/platforms/zworkforce/infrastructure/cilium/
```

### Phase 6: Merge shared tooling

```bash
# Scripts (deduplicate)
rsync -av --ignore-existing scripts/ /home/cvsz/platforms/zworkforce/scripts/
# Tools
rsync -av --ignore-existing tools/ /home/cvsz/platforms/zworkforce/tools/
# Deploy (merge Dockerfiles)
rsync -av deploy/ /home/cvsz/platforms/zworkforce/deploy/
# Schemas
rsync -av schemas/ /home/cvsz/platforms/zworkforce/schemas/
# Automation
rsync -av automation/ /home/cvsz/platforms/zworkforce/automation/
```

### Phase 7: Update imports and references

1. Update all `@z-platform/*` imports to relative paths or `@zworkforce/*`
2. Update `docker-compose.yml` service names and build contexts
3. Update environment variable prefixes (`Z_PLATFORM_*` → `ZWORKFORCE_*`)
4. Update health check endpoints
5. Update Caddyfile/nginx configs

### Phase 8: Consolidate compose files

Merge `compose.yml`, `compose.zarvis-local.yml`, `compose.zarvis-owner-domain.yml` into zworkforce's `compose.yaml`.

### Phase 9: Update CI/CD

1. Merge `.github/workflows/` from both repos
2. Update build matrices to include services and apps
3. Consolidate test pipelines

### Phase 10: Cleanup

1. Archive z-platform repo (read-only)
2. Update documentation
3. Update README with new structure
4. Remove duplicate configs

## Post-Migration Structure

```
zworkforce/
├── api/                    # Python API (existing)
├── worker/                 # Python worker (existing)
├── cmd/                    # CLI tools (existing)
├── services/               # NEW: Node.js services from z-platform
│   ├── ai-gateway/
│   ├── agent-orchestrator/
│   ├── zarvis-action-gateway/
│   └── ...
├── apps/                   # NEW: Frontend apps from z-platform
│   ├── zarvis-console/
│   ├── zchat/
│   └── ...
├── packages/               # Existing product suites
│   ├── zarvis/
│   ├── zeto/
│   ├── zider/
│   ├── zsp-aitool/
│   └── contracts/          # NEW from z-platform
├── infrastructure/         # Merged K8s/Terraform
├── deploy/                 # Merged Dockerfiles
├── scripts/                # Merged scripts
├── automation/             # Merged automation
└── docs/                   # Merged documentation
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Import breakage | Use codemod to update `@z-platform/*` → relative imports |
| Compose conflicts | Namespace service names (`zp-` prefix during transition) |
| Env var conflicts | Prefix all z-platform vars with `ZP_` during migration |
| CI breakage | Run both CI systems in parallel during transition |
| Service downtime | Blue-green deploy: run both repos, cut over DNS |
| Lockfile conflicts | Regenerate pnpm-lock.yaml after merge |

## Validation Checklist

- [ ] All services start via `docker compose up`
- [ ] All apps build successfully
- [ ] All tests pass (Python + Node.js)
- [ ] Health checks return 200
- [ ] Cloudflare Tunnel routes all domains
- [ ] CI/CD pipelines green
- [ ] Documentation updated
- [ ] z-platform archived
