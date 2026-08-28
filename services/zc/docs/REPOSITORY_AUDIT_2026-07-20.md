# Repository Audit and Remediation Report — 2026-07-20

## Executive summary

This report covers the repository-wide audit and remediation performed on branch `codex/fix-dev-httpx-dependency` for PR #11.

The original CI blocker was the invalid `httpx2` development dependency. The remediation was expanded to address the material packaging, runtime, Docker, CI, security, reliability, and documentation inconsistencies found during the audit.

## Remediation status

| Finding | Severity | Status | Resolution |
|---|---|---|---|
| Invalid `httpx2` dependency | P0 | Fixed | Replaced with `httpx>=0.27.0` |
| Broken `zc`/`zcoder` entry points | P0 | Fixed | Added stable `app.main:cli` and package-install smoke tests |
| Product identity conflict | P0 | Fixed for supported runtime | Canonical identity is `zcoder`; legacy `/v1/wire` routes remain for compatibility |
| Version conflict | P1 | Fixed for supported runtime | Package, API, Docker, and living docs use `1.33.0` |
| Port mismatch | P1 | Fixed | Local, CLI, Docker, CI, and docs use HTTP port `8000` |
| Readiness hid startup failures | P1 | Fixed | Added structured component state and optional strict HTTP 503 behavior |
| Print-based lifecycle logging | P1 | Fixed | Replaced lifecycle prints with Python logging |
| Unsafe/invalid CORS defaults | P1 | Fixed | Production enables no cross-origin callers; debug wildcard has credentials disabled |
| Nondeterministic `apt-get upgrade` | P1 | Fixed | Removed unrestricted OS upgrade from Docker build |
| Changed-file-only Bandit gate | P1 | Fixed for supported runtime | CI scans all of `app/` with Bandit |
| Missing package regression coverage | P1 | Fixed | CI installs package and runs `zc --help` and `zcoder --help` |
| Documentation commands did not match code | P1 | Fixed | README and Quickstart now use executable commands and verified endpoints |
| Broad legacy lint/security suppressions | P2 | Partially mitigated | Supported `app/` runtime is fully scanned; legacy trees still require incremental cleanup |
| Lock files, SBOM, provenance | P2 | Open | Release-engineering work remains |
| Multiple source/product trees | P2 | Open | Requires architecture decision and migration plan |

## Canonical supported runtime contract

- Product and package: `zcoder`
- Version: `1.33.0`
- Python: 3.11 and 3.12
- Installed commands: `zc`, `zcoder`
- Application: `app.main:app`
- HTTP port: `8000`
- Readiness: `GET /ready`
- Liveness: `GET /v1/wire/health/live`
- Legacy route prefix: `/v1/wire`, retained for backward compatibility

## Reliability behavior

Application lifespan records state for:

- Redis cache
- shared HTTP client
- upload manager
- optional gRPC server

Readiness returns a component map and a list of failed components.

- `STRICT_READINESS=false`: degraded optional integrations return HTTP 200 with `status: degraded`.
- `STRICT_READINESS=true`: any enabled failed component returns HTTP 503.
- The standalone Docker profile disables Redis, protobuf/gRPC, NATS, and OpenTelemetry by default so the image has an explicit dependency-free baseline.

## Security improvements

- Production CORS no longer uses the invalid `http://localhost:*` pattern.
- Wildcard development origins are never combined with credentialed CORS.
- Container execution remains non-root and uses a non-login shell.
- Docker health checks use loopback and the canonical readiness endpoint.
- CI runs Bandit across the full supported `app/` runtime rather than only changed files.
- CI keeps CodeQL and adds package and container smoke validation.

## CI definition of done

The updated workflow requires:

1. Ruff over the repository.
2. Black over `app/` and `tests/`.
3. mypy.
4. Bandit over all of `app/`.
5. Package installation and console-command smoke tests.
6. pytest on Python 3.11 and 3.12.
7. Web application tests.
8. Coverage artifact generation.
9. Docker build, container start, readiness, and liveness checks.
10. CodeQL through the existing workflow.

## Documentation policy

Living documents updated by this remediation:

- `README.md`
- `QUICKSTART.md`
- this audit report

Historical upgrade reports, phase-completion records, and `.zc/skills/**/SKILL.md` files are not mass-rewritten. They are point-in-time evidence or operational agent instructions and should change only through explicit correction notices or corresponding behavior changes.

## Residual risks and next work

### Release reproducibility

- Generate hash-locked production dependencies.
- Pin critical GitHub Actions to reviewed commit SHAs.
- Produce SBOM and provenance attestations.
- Sign or otherwise attest release images.

### Legacy tree consolidation

The repository still contains overlapping surfaces under `app/`, `src/wire/`, `webapp/`, and `.zc/`. A formal architecture decision should classify each as supported, experimental, legacy, or separately packaged.

### Suppression cleanup

Global Ruff and Bandit exceptions outside the supported runtime should be replaced incrementally with narrow, justified suppressions. The new full `app/` Bandit gate prevents new supported-runtime regressions while legacy cleanup proceeds.

### Benchmark evidence

Historical numerical performance claims are not considered current production evidence. A future benchmark report should version:

- workload and dataset
- hardware and operating system
- dependency lock
- commands and configuration
- raw results
- statistical method
- CI artifact links

## Audit limitations

This work is a repository, code, packaging, container, CI, and documentation audit. It is not a production penetration test, load test, chaos exercise, Kubernetes deployment certification, or validation of external provider behavior.
