---
name: zworkforce-release-verification
description: Verify zWorkforce release candidates, tags, CI status, SBOMs, checksums, changelog, version metadata, deployment manifests, Windows artifacts, GHCR packages, and rollback evidence before publishing or merging release work.
---

# zWorkforce Release Verification

Treat releases as evidence-driven. Do not infer artifact existence from docs or
workflow intent.

## Checklist

1. Confirm version consistency in `pyproject.toml`, `README.md`,
   `CHANGELOG.md`, release docs, deployment manifests, and examples.
2. Run `python3 scripts/verify_release.py --expected <version>`.
3. Run the Python unit suite and compile check.
4. Inspect GitHub Actions for CI, CodeQL, dependency review, release,
   container, PostgreSQL, security, and Windows-client jobs.
5. Verify release artifacts, SBOM/checksum/provenance, GHCR image tags, and
   Windows MSIX/MSIXBundle only from actual outputs.
6. Record rollback path, migration safety, backup requirements, and operator
   sign-off gaps.

## Output

Return a release decision:

- `GO`: all required local and remote evidence is present.
- `NO-GO`: a blocking gap exists.
- `CONDITIONAL`: safe only after named external evidence or approval.

Include commands run, GitHub checks inspected, artifact identifiers, and missing
evidence.
