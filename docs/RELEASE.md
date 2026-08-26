# Release Process

zWorkforce releases are tag-driven and must originate from a commit reachable from `main`.

## Preconditions

Before creating a release tag:

1. Merge the intended release commit to `main`.
2. Confirm CI, Windows client, Dependency Review, CodeQL, and every affected path-filtered package workflow are green.
3. Confirm `pyproject.toml`, `zworkforce.__version__`, Makefile, dashboard, Compose/Kubernetes image references, publication defaults, and `CHANGELOG.md` carry the same version.
4. Run `python scripts/verify_release.py` locally or rely on the mandatory CI release-integrity job.
5. Confirm production migration/rollback notes are current and complete the mandatory environment evidence in `docs/PRODUCTION-EVIDENCE.md`.
6. Run `pnpm peers check` from `packages/zarvis` when Z.A.R.V.I.S. paths changed and reject dependency updates with unresolved peer constraints.
7. Confirm the Z.A.R.V.I.S. API audit and test suite pass for the exact release commit when those paths changed.
8. Reconcile `.github/rulesets/main.json` with the server-side GitHub Ruleset using repository administration permissions; the checked-in desired-state file alone is not proof that GitHub enforcement is active.

## Tag format

Use an immutable semantic version tag:

```bash
git checkout main
git pull --ff-only
git tag -a v3.0.4 -m 'zWorkforce v3.0.4'
git push origin v3.0.4
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

The workflow stages the Python artifacts and the trusted Windows MSIX in
separate jobs, then publishes the GHCR image and GitHub Release after the
Python release gate passes. The Windows job builds an unsigned package and
signs that exact file with Azure Artifact Signing through GitHub Actions OIDC;
it verifies the signature, timestamp, publisher, package identity and hash
before running the install smoke test. Windows MSIX artifacts are attached only
when the Azure signing configuration is present; if it is absent, the release
publishes the Python artifacts, SBOM, checksums, container image and release
notes without Windows packages. Partial Azure configuration fails closed. The
publish job creates an empty `windows-assets` staging directory when the
optional Windows artifact download is skipped, so non-Windows release assets
remain publishable.

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

The pull-request Windows workflow deliberately uses a short-lived development
certificate for package installation smoke tests. Production release signing
is post-build and uses Azure Artifact Signing, so the private signing key stays
inside the managed signing service and is never placed in the repository,
GitHub Secrets, or the Windows checkout.

The protected release environment must provide these GitHub Secrets:

- `AZURE_CLIENT_ID`;
- `AZURE_TENANT_ID`; and
- `AZURE_SUBSCRIPTION_ID`.

It must also provide these GitHub Actions variables:

- `AZURE_ARTIFACT_SIGNING_ENDPOINT` (HTTPS);
- `AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME`;
- `AZURE_ARTIFACT_SIGNING_PROFILE_NAME`; and
- `WINDOWS_MSIX_PUBLISHER`, exactly matching the verified certificate subject.

The Azure identity must have a federated credential for this repository and the
minimum Artifact Signing permissions on the account/profile. The publisher
identity verification and certificate profile are operator-owned Azure
provisioning prerequisites; repository code cannot create or substitute them.
The workflow builds with `Package-Client.ps1 -Unsigned`, signs with
`azure/artifact-signing-action@v2` using SHA-256 and an RFC 3161 timestamp, then
verifies the real package before upload. The uploaded `.cer` contains only the
public signer certificate. PFX/self-signed paths remain development/test-only
and are not accepted as production Stage H evidence.

The manual external Stage H verifier additionally reads `WINDOWS_HOST`,
`WINDOWS_REPO_DIR`, `WINDOWS_MSIX_PUBLISHER`,
`WINDOWS_MSIX_EXPECTED_SHA256`, and `ZWORKFORCE_HTTPS_ENDPOINT` from the local
operator environment. `WINDOWS_MSIX_PATH` may point to an explicitly staged
signed package; otherwise the verifier requires exactly one matching package in
`ZWorkforceClient/out/Release-x64`. Keep these values in the ignored
`.env.release`, and populate the hash only from the final signed artifact.

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
