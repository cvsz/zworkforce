# AGENTS.md

## Release status
Repository release candidate: `v3.0.4`.

`v3.0.4` repository work and production-environment completion are separate gates. The repository candidate may be complete while operator-owned external evidence in `docs/PRODUCTION-EVIDENCE.md` remains pending. Do not create/tag the immutable `v3.0.4` release until repository policy, exact-candidate checks/reviews, mandatory external evidence and the GO decision permit it.

Forward feature plans under `planning/` (including Z.A.R.V.I.S., Zeto, Zider, zsp-aitool, router, Hermes/Spawn and Skywork-inspired workspace upgrades) are not automatically `v3.0.3` release blockers. Treat an item as a current-release blocker only when `ROADMAP.md`, `planning/exec-planning-zwf.md`, `docs/PRODUCTION-EVIDENCE.md`, a failing required check/security finding, or an explicit master-plan requirement binds it to the `v3.0.3` candidate. Never mark forward work complete merely to make release status green.

Use `planning/RELEASE-SCOPE-STATUS.md` as the normalized subsystem classification overlay for release triage. It does not replace subsystem Definitions of Complete; it translates broad feature-plan labels such as `Active`, `Production Target`, and `Integrated` into the four-state current-release vocabulary defined by `ROADMAP.md`.

## Repository intent
zWorkforce is a production AI Workforce control plane. Changes must preserve tenant isolation, server-side secrets, bounded execution, explicit mutation authorization and durable state transitions.

## Required validation

```bash
python -m compileall -q zworkforce tests
PYTHONPATH=. python -m unittest discover -s tests -v
zworkforce doctor
```

PostgreSQL changes must also run `tests/test_v3_postgres.py` against a real PostgreSQL service. Runtime changes must not introduce `shell=True` or expose provider secrets in static assets.

## Architecture rules
- Browser/static code never receives provider/storage/database credentials.
- Durable state changes go through repository methods.
- Mutating tools stay deny-by-default and bounded.
- Preserve SQLite compatibility unless a change is explicitly PostgreSQL-only.
- Distributed queue code must be transactional and idempotent.
- Do not claim external infrastructure is provisioned merely because an adapter exists.