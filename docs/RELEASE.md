# Release Process

zWorkforce releases are tag-driven and must originate from a commit reachable from `main`.

## Preconditions

Before creating a release tag:

1. Merge the intended release commit to `main`.
2. Confirm CI, Windows client, Dependency Review, CodeQL, and every affected path-filtered package workflow are green.
3. Confirm `pyproject.toml`, `zworkforce.__version__`, Makefile, dashboard, Compose/Kubernetes image references, publication defaults, and `CHANGELOG.md` carry the same version.
4. Run `python3 scripts/verify_release.py` (fallback: `python` where `python3` is unavailable) locally or rely on the mandatory CI release-integrity job.
5. Confirm production migration/rollback notes are current and complete the mandatory environment evidence in `docs/PRODUCTION-EVIDENCE.md`.
6. Run `pnpm peers check` from `packages/zarvis` when Z.A.R.V.I.S. paths changed and reject dependency updates with unresolved peer constraints.
7. Confirm the Z.A.R.V.I.S. API audit and test suite pass for the exact release commit when those paths changed.
8. Reconcile `.github/rulesets/main.json` with the server-side GitHub Ruleset using repository administration permissions; the checked-in desired-state file alone is not proof that GitHub enforcement is active.

## Tag format

Use an immutable semantic version tag:

```bash
git checkout main
git pull --ff-only
git tag -a v3.0.3 -m 'zWorkforce v3.0.3'
git push origin v3.0.3
```

Do not move or reuse an existing release tag. Publish a new patch/minor/major version instead.

## Automated release outputs

`.github/workflows/release.yml` validates the tag against package metadata and verifies that the tagged commit is reachable from `main`. If validation succeeds it produces:

- source distribution (`sdist`);
- Python wheel;
- CycloneDX JSON SBOM;
- SHA-256 checksums;
- GitHub artifact bundle;
- GitHub build-provenance attestation for distribution artifacts;
- GHCR image tagged with the release tag and `latest`;
- OCI provenance and SBOM from BuildKit;
- GitHub Release with generated release notes and attached artifacts.

The workflow stages the Python artifacts and trusted Windows MSIX in separate
jobs, then publishes the GHCR image and GitHub Release after the Python release
gate passes. Windows MSIX artifacts are attached only when trusted signing
secrets are configured; if those secrets are absent, the release publishes the
Python artifacts, SBOM, checksums, container image and release notes without
Windows packages. The publish job creates an empty `windows-assets` staging
directory when the optional Windows artifact download is skipped, so unsigned
repositories can still publish the non-Windows release assets.

Production deployments should pin the semantic tag or image digest, never `latest`.

The `packages/zarvis` tree is shipped from the same immutable repository commit.
Its package manifests, lockfile, Windows artifacts, release-governance records,
and service images must therefore be validated before the root release tag is
created when those paths changed; a green root Python build alone is not a
release approval.

## Manual container-only publication

`.github/workflows/publish-container.yml` exists for controlled repair/replay of
the GHCR artifact independently of the normal release workflow. It requires
`ref == v<version>`, checks that the immutable tag is reachable from `main`,
runs `scripts/verify_release.py --expected <version>`, and refuses to overwrite
existing immutable semantic image tags.

Do not use the manual container workflow to publish an unmerged candidate or to
bypass missing production evidence. The normal tag-driven release remains the
canonical release path.

## Trusted Windows signing

The pull-request Windows workflow deliberately uses a short-lived self-signed
certificate for package installation smoke tests. A release tag publishes
Windows MSIX artifacts only when the repository or protected release
environment provides:

- `WINDOWS_MSIX_PFX_BASE64`: base64-encoded organization-issued MSIX signing
  PFX containing its private key;
- `WINDOWS_MSIX_PFX_PASSWORD`: the PFX password; and optionally
- `WINDOWS_MSIX_PUBLISHER`: the exact certificate subject to use as the MSIX
  publisher (otherwise the package script derives it from the certificate).

The release workflow imports the PFX only on the ephemeral Windows runner,
patches the package publisher to match the signing identity, and publishes
only the public `.cer` beside the MSIX. Never commit the PFX, password, or a
base64 value to the repository. Missing signing secrets skip Windows artifacts;
invalid signing secrets still fail the Windows job instead of producing a
package that users cannot trust.

## Release verification

After the workflow finishes:

1. Inspect the GitHub Release and workflow conclusion.
2. Verify downloaded files against `SHA256SUMS`.
3. Inspect provenance/attestation in GitHub Actions.
4. Pull the exact image tag/digest and run `zworkforce --version`.
5. Deploy first to a staging environment backed by PostgreSQL.
6. Run `zworkforce doctor` and `scripts/smoke-test.sh`.
7. Exercise one durable task, one workflow, one approval path, scheduler occurrence deduplication, and outbox claim/retry behavior before promotion.
8. Record the exact candidate SHA, workflow/check URLs, GHCR digest, checksums, and external environment drill evidence in `docs/PRODUCTION-EVIDENCE.md` or the immutable release record.

## Hotfixes

Hotfixes use the same flow. Create a branch from the affected release/main state, fix and validate it, merge to `main`, bump the patch version, update `CHANGELOG.md`, then publish a new immutable tag.

## Rollback

Application rollback is performed by redeploying the previous immutable image tag/digest. Database rollback is a separate destructive operation and must follow `docs/DISASTER-RECOVERY.md`; do not restore a database merely to roll back application code unless data/schema compatibility requires it.

## External publication

The repository release workflow publishes to GitHub Releases/GHCR. Publishing to PyPI or another registry is intentionally not automatic until trusted-publishing ownership and release policy for that external registry are configured.

For repository-level release operations, branch/check expectations, package
cleanup, and GitHub alert triage, see [GITHUB-OPERATIONS.md](GITHUB-OPERATIONS.md).
