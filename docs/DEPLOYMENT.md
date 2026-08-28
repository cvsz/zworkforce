# Deployment

## Local development

Use SQLite and embedded workers. Local development is not a substitute for PostgreSQL-backed distributed validation before a production release.

## Single-host production

Use Docker Compose with PostgreSQL, API, worker and scheduler. Optional outbox runs under the `integrations` profile.

For source builds:

```bash
export ZWORKFORCE_POSTGRES_PASSWORD='replace-me'
export ZWORKFORCE_API_KEYS='replace-me:superadmin:default:bootstrap:*'
docker compose up -d --build
```

For an immutable published release, set `ZWORKFORCE_IMAGE` and do not rebuild on the production host:

```bash
export ZWORKFORCE_IMAGE=ghcr.io/cvsz/zworkforce:v3.0.4
docker compose pull
docker compose up -d --no-build
```

The production control-plane hostname for this deployment is
`https://zwf.zeaz.dev`. The Cloudflare Tunnel must route that exact hostname
to the host origin at `http://127.0.0.1:9570`. The container API still listens
on port `9569`; the host-port split keeps `9569` available for the separate
zksato service. Keep the API bound to the loopback/network boundary and do not
publish PostgreSQL or worker ports.
The API alias `https://zwf-api.zeaz.dev` uses the same reviewed tunnel origin
and may be used by API clients; it does not create a second runtime or bypass
the existing authentication and tenant controls.
The `https://zslog.zeaz.dev` hostname is the separate zslog fake-credit
realtime log service. It must route to `http://127.0.0.1:9581`; the service is
loopback-only, demo-only, and does not connect to external games or handle real
currency.
After the origin is running, verify the public path with:

```bash
ZWORKFORCE_BASE_URL=https://zwf.zeaz.dev bash scripts/smoke-test.sh
```

Use `.env.production.example` as a field inventory only; replace all placeholders and keep the real environment file outside Git.

## Kubernetes

`deploy/kubernetes` provides:

- namespace/config/secret example;
- two API replicas;
- two worker replicas + HPA;
- leased scheduler replicas;
- claim-based outbox replicas with at-least-once delivery;
- PDBs;
- non-root/read-only/capability-drop security contexts;
- workspace/artifact PVCs;
- default-deny network policy;
- immutable `v3.0.4` GHCR image references for this release candidate.

```bash
kubectl apply -k deploy/kubernetes
```

Supply `ZWORKFORCE_DATABASE_URL`, API keys and provider credentials through a real secret manager/injector. Replace example secret manifests before deployment. See `docs/SECRET-MANAGEMENT.md`.

Production configuration rejects the mock provider. `zworkforce doctor` checks
database, workspace, audit-chain and provider readiness, but a successful
doctor run is not a model-generation smoke test; run the authenticated smoke
test before promotion.

### Required network work

The supplied NetworkPolicy denies all egress. Add explicit egress for:

- PostgreSQL;
- model providers;
- OIDC discovery/JWKS;
- OTLP collector;
- S3/Qdrant/embedding endpoints;
- approved tool destinations and remote registries.

Do not weaken the policy to unrestricted egress solely to make a dependency work; document each destination and owner.

## Verification

After every deployment:

```bash
zworkforce doctor
ZWORKFORCE_BASE_URL=https://zwf.zeaz.dev bash scripts/smoke-test.sh
```

If the smoke path requires API authentication, also set `ZWORKFORCE_API_KEY`.

Production promotion should satisfy every item in `docs/PRODUCTION-READINESS.md` and record the environment-specific proof in `docs/PRODUCTION-EVIDENCE.md` or an immutable release/incident record. CI simulations do not prove that external PostgreSQL HA/PITR, IdP, provider, S3/Qdrant, OTLP, DNS/ingress, or alert-routing infrastructure exists or has been exercised.

## Backup and recovery

Use `scripts/backup-postgres.sh` and `scripts/restore-postgres.sh` for repository-supported logical backup/restore procedures. Managed PostgreSQL should also use provider-native PITR/snapshots. Full procedures are in `docs/DISASTER-RECOVERY.md`.

## Release artifacts

Stable `vX.Y.Z` tags trigger `.github/workflows/release.yml`, which verifies main ancestry/version consistency and publishes Python distributions, SHA-256 checksums, CycloneDX SBOM, provenance attestations, GHCR images and a GitHub Release. See `docs/RELEASE.md`.

## External HA boundary

zWorkforce application processes are horizontally scalable. PostgreSQL, ingress/DNS, object/vector stores, secret managers, identity providers and observability backends require their own HA, backup and disaster-recovery design. The repository provides integration boundaries and runbooks but does not claim those managed services are provisioned without operator accounts/credentials.
