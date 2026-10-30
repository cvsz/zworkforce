# ZAPK / zWorkforce monorepo deployment

Validated repo convention: npm workspace `apps/*`, services `services/*`, packages `packages/*`.
This package should be installed as `apps/zapk` in a dedicated PR, not inside the zWorkforce core.
Runtime is Python 3.12 FastAPI; the zWorkforce control plane remains independent.

## Host configuration
1. Copy project into `apps/zapk` in a clean branch.
2. Create `.env` from `.env.zapk.example`. Generate two distinct random secrets using `openssl rand -hex 32`. Never commit `.env`.
3. Run `docker compose -f compose.zapk.yaml config -q`.
4. Run `docker compose -f compose.zapk.yaml up -d --build`.
5. Verify `curl -f http://127.0.0.1:18080/zapk/api/health`.
6. Confirm the owning reverse proxy for `zwsl.zeaz.dev` and stage the provided `nginx.zapk.conf.example` locations. Run `nginx -t` before reload.
7. Verify `curl -f https://zwsl.zeaz.dev/zapk/api/health` and load the UI.

## Security gates before public launch
- Reverse proxy per-IP request and upload rate limits; WAF.
- Real package signature analysis and malware detection; human review evidence before calling a build safe.
- Per-publisher identity, scoped authorization, verified ownership, audit log and immutable approvals.
- PostgreSQL + object storage, transaction-safe upload workflow, upload quotas, resumable objects, file retention.
- Version pinning, SBOM, vulnerability scan, CI, recovery testing, observability and alerting.
- Validate domain ownership/Terraform boundaries; do not modify Cloudflare routes without an approved plan.

## Rollback
Use previous image digest and `docker compose -f compose.zapk.yaml up -d --no-deps zapk`. Do not delete volumes. Backup the persistent `zapk_data` volume before migration.
