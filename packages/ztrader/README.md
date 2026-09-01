# zTrader

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

Last updated: 2026-06-11

`apps/ztrader` is the safety-first multi-language algorithmic trading platform stack and the active merge target for archived source material under `.ops/backups`.

## Merge status

```text
STATUS: MERGE IMPLEMENTATION STARTED
SOURCE MATERIAL: retained until validation passes
TARGET: apps/ztrader
PLAN: reports/merge/ztrader-source-merge-report.md
```

Source material is retained during migration. The active application layout remains under `apps/ztrader`; archived source names are not recreated as application folders.

## Stack

| Layer | Stack |
|---|---|
| Frontend | Next.js / TypeScript / i18n dependencies |
| Backend | FastAPI / Python |
| Workers | Celery-style async orchestration |
| Data | PostgreSQL-oriented backend storage |
| Queue/cache | Redis |
| Trading adapter | CCXT shell + safe mock fallback |
| Paper execution | deterministic paper engine |
| Risk gate | fail-closed risk engine with symbol allowlist, max notional, global kill switch |
| Deployment | Docker Compose |
| App areas | `frontend/`, `backend/`, `scripts/`, `harness/`, `reports/merge/` |

## Safety mode

Use paper/dry-run workflows by default. Live trading must remain explicitly gated by risk controls, environment flags, and operator review.

Default safety expectation:

```text
EXECUTION_MODE=paper
LIVE_TRADING_ENABLED=false
GLOBAL_KILL_SWITCH=true
```

## Merge workflow

Preview source mapping:

```bash
cd /home/zeazdev/zeaz-platform/apps/ztrader
make merge-dry-run
```

Apply source mapping into zTrader while retaining original source apps:

```bash
make merge-apply
```

Validate after mapping:

```bash
make merge-validate
make merge-report
```

Generated reports live in:

```text
apps/ztrader/reports/merge/
```

## Source mapping summary

### Platform Archive

| Source | Target |
|---|---|
| platform configs | `apps/ztrader/config/integrations/` |
| `.ops/backups/ABTPi18n/core/` | `apps/ztrader/backend/src/ztrader/abt/core/` |
| platform strategies | `apps/ztrader/backend/src/ztrader/strategies/external/` |
| platform monitoring | `apps/ztrader/backend/src/ztrader/monitoring/trading/` |
| platform scripts | `apps/ztrader/scripts/integrations/` |
| platform tests | `apps/ztrader/backend/tests/integrations/` |
| metadata files | `apps/ztrader/merge-sources/platform/` |

### Market Archive

| Source | Target |
|---|---|
| market source package | `apps/ztrader/backend/src/ztrader/market/` |
| market harness | `apps/ztrader/harness/trading/` |
| market tests | `apps/ztrader/backend/tests/market/` |
| market reports | `apps/ztrader/reports/trading/` |
| market scripts | `apps/ztrader/scripts/market/` |
| market migrations | `apps/ztrader/backend/alembic/source/` |
| metadata/Docker files | `apps/ztrader/merge-sources/market/` |

The backend uses `PYTHONPATH=backend/src:backend/src/ztrader/abt` so `ztrader` and compatibility imports resolve during local tests and container runtime.

## Local development

```bash
cd /home/zeazdev/zeaz-platform/apps/ztrader
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Docker

```bash
cd /home/zeazdev/zeaz-platform/apps/ztrader
docker compose up -d --build
```

## Operator commands

```bash
make help
make validate-local
make test-backend
make run-docker
make stop-docker
make server-start
make server-status
make server-stop
```

## Important files

```text
frontend/
backend/
scripts/merge-sources.sh
docker-compose.yml
Makefile
README.md
SECURITY.md
reports/merge/
```

## Completion gates before source cleanup

- `make merge-apply` completed locally.
- `make merge-validate` passes.
- Platform archive source-only features are mapped or intentionally archived.
- Market archive source-only features are mapped or intentionally archived.
- Final report exists under `apps/ztrader/reports/merge/`.
- Root README and zTrader README reflect the final state.
- No imports or operational docs require the old source paths.

## Security notes

- Never commit exchange API keys, wallet secrets, provider tokens, or database passwords.
- Keep live trading disabled unless explicitly audited.
- Use paper mode for tests and demos.
- Keep the global kill switch enabled by default.
- Require risk gate validation before external exchange actions.
