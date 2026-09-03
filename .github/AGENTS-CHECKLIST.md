# AGENTS Checklist — PR & Merge Guidance

Purpose: A short, copy-paste checklist that must be satisfied by PR authors before requesting review/merge. This codifies the non‑negotiable rules from AGENTS.md to make review gating explicit.

## PR author checklist (attest and complete)
- [ ] I have run the required local validation commands (see below) and included CI run references in the PR description.
- [ ] No secrets, provider keys, service tokens, wallet keys, card data, or production identifiers are committed.
- [ ] Browser/static assets do NOT contain provider, storage, or database credentials or secrets.
- [ ] No code introduces `shell=True`, unbounded subprocess calls, or unsafe shell interpolation.
- [ ] Mutating tools / actions remain deny-by-default; any granted mutation authority is documented and audited in the PR.
- [ ] Durable state updates are implemented via repository methods only (no direct DB file edits or undocumented schema changes).
- [ ] SQLite compatibility is preserved unless the PR is explicitly PostgreSQL-only and documents why.
- [ ] Distributed queue changes are transactional and idempotent; tests cover concurrency/failure cases where applicable.
- [ ] New or modified external adapters do NOT assert external infrastructure is provisioned; deployment/provisioning evidence is operator-owned.
- [ ] I updated or added tests for success, failure, authorization, timeout, and denial paths when behavior changed.
- [ ] I updated docs where architecture, operations, requirements, or security boundaries changed.

## Required local validation (run before pushing)
```bash
python -m compileall -q zworkforce tests
PYTHONPATH=. python -m unittest discover -s tests -v
zworkforce doctor
```
- If you change PostgreSQL-related code, also run: `python -m pytest tests/test_v3_postgres.py` against a real PostgreSQL service (not SQLite).

## Reviewer guidance (quick scan)
- Confirm the above attestations are checked in the PR description or the author has documented justification for any exceptions.
- Verify CI includes Python compile/tests and `zworkforce doctor` runs on the exact merge commit.
- For DB changes, ensure Postgres integration tests ran against a real Postgres instance and results are included.
- Confirm there are no plaintext credentials, secrets, or operator-owned identifiers in the diff.
- Check for unsafe subprocess usage, `shell=True`, or direct OS calls that can be replaced with safer library APIs.

## When to escalate
- If you find committed credentials, secrets, or provider tokens: mark the PR as security-blocked and request a secret-scan/rotation run.
- If production topology or external evidence is required for the change (see planning/RELEASE-SCOPE-STATUS.md and docs/PRODUCTION-EVIDENCE.md), tag the release authorities and do NOT create a release tag until operator evidence is recorded.

## Notes
- This checklist captures the non-negotiable AGENTS.md rules; it does not replace subsystem DOCCs or planning documents. For release-scoping decisions consult `planning/RELEASE-SCOPE-STATUS.md` and `docs/PRODUCTION-EVIDENCE.md`.

