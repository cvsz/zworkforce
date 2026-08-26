# GitHub Operations

This document is the repository-facing operations runbook for
`github.com/cvsz/zWorkforce`. It covers GitHub controls and automation only;
runtime deployment and disaster recovery are covered by the other operations
documents.

## Branches and pull requests

- `main` is the only long-lived branch.
- Feature, fix, and maintenance branches must be short-lived and deleted after
  merge.
- Use reviewed pull requests for all production-impacting changes.
- Prefer signed commits for local work. Squash merges from GitHub are accepted
  when the merge commit is produced by GitHub and all required checks pass.
- Do not force-push `main` or reuse a release tag.

Before merging a pull request, verify:

1. CI, CodeQL, Dependency Review, Windows client, and any affected package workflows are green.
2. Review threads are resolved.
3. Documentation, release notes, and runbooks are updated when behavior,
   operations, workflows, packages, or security posture changed.
4. No credentials, private keys, customer data, generated secret files, or
   local environment files are committed.

## Required checks and ruleset contract

The desired default-branch release-protection contract is versioned in
[`.github/rulesets/main.json`](../.github/rulesets/main.json). The file is a
repository-side desired state: it must be reconciled with GitHub Rulesets by an
operator or automation that has repository administration permission. Merely
committing the JSON does not prove the server-side ruleset is applied.

As of 2026-08-18 the server-side ruleset is applied on the default branch as
ruleset ID **`20988030`** (`zWorkforce main release protection`, enforcement
`active`) and is regression-checked against the committed contract. A
Copilot-review ruleset (ID `20673774`) also applies to the default branch.
If the server-side ruleset is recreated, replaced, or drifted, verify the
committed JSON still matches the applied rules before relying on release
gates.

Global required checks must only include checks that are emitted for every pull
request. In particular, `ZARVIS` uses path filters and its package-specific jobs
must **not** be configured as global required contexts; they are mandatory when
the workflow is triggered by affected paths.

The repository uses these GitHub Actions as release and merge evidence:

| Workflow | Purpose |
| --- | --- |
| `CI` | Python 3.12/3.13/3.14 tests, PostgreSQL integration, documentation/repository policy, release integrity, container build, security invariants. |
| `ZARVIS` | Z.A.R.V.I.S. package migration contract, Node workspace tests, API tests/audit, Windows restore checks for affected paths. |
| `Windows client` | Native client restore, build, core tests, MSIX package, launch smoke check, artifact upload. |
| `Windows signed candidate` | Manually signs a full-SHA `main` candidate with Azure Artifact Signing for pre-tag Stage H evidence; never publishes a release or image. |
| `CodeQL Advanced` | Static analysis for Actions and Python surfaces. |
| `Dependency Review` | Blocks vulnerable or disallowed dependency changes in pull requests. |
| `Automatic Dependency Submission` | Submits dependency graph data for NuGet and related ecosystems. |

The canonical globally required contexts are recorded in the ruleset contract
and regression-tested by `tests/test_repository_policy.py`. If a workflow or
job is added, renamed, path-filtered, or removed, update the ruleset contract,
this table, and the policy test in the same pull request.

## Dependency maintenance

Dependabot coverage is declared in `.github/dependabot.yml` for:

- root Python package;
- GitHub Actions;
- root Docker build;
- `ZWorkforceClient` NuGet dependencies;
- `packages/zarvis` Node workspace;
- `packages/zarvis/services/zarvis-api` Python API dependencies;
- `packages/zarvis/tools/zctl` Go module;
- `packages/zarvis/apps/zarvis-windows` NuGet dependencies.

For dependency pull requests:

1. Read the upstream changelog/security advisory before merging major updates.
2. Keep peer dependency ranges compatible with accepted major versions.
3. Regenerate lockfiles only with the repository package manager.
4. Run the package-specific tests and audits named in the pull request
   template.
5. Close or supersede duplicate Dependabot PRs after a consolidated update
   lands.

## Security alerts

Triage GitHub security signals in this order:

1. Secret scanning alerts: rotate the exposed secret first, then remove the
   source and document the incident.
2. Code scanning alerts: reproduce the path locally, add a regression test
   when practical, and keep the alert open until the fix is merged.
3. Dependabot alerts: patch directly or merge the generated PR after CI passes.
4. Dependency Review failures: inspect the blocked package and decide whether
   to update, pin, replace, or explicitly reject the dependency.

Do not dismiss alerts as false positives without a short justification tied to
the exact code path or package version.

## Releases and packages

Stable release tags are `vX.Y.Z` and trigger `.github/workflows/release.yml`.
The release workflow verifies tag/version consistency, builds Python
distributions, produces checksums and a CycloneDX SBOM, attests provenance,
publishes the GHCR image, and creates or updates the GitHub Release.

`.github/workflows/publish-container.yml` is the guarded manual container-only
publication path. Its `ref` must exactly equal `v<version>`, the tag must resolve
to a commit on `main`, `scripts/verify_release.py` must pass from that tag, and
existing immutable semantic image tags are refused rather than overwritten.
Use this workflow only when a container publication must be repaired or
replayed independently of the normal tag-driven release; it is not a shortcut
around the release evidence gate.

The Windows MSIX release artifact is optional and requires Azure Artifact
Signing configured for GitHub Actions OIDC:

- Secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID`;
- Variables: `AZURE_ARTIFACT_SIGNING_ENDPOINT`,
  `AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME`,
  `AZURE_ARTIFACT_SIGNING_PROFILE_NAME`, and `WINDOWS_MSIX_PUBLISHER`.

The Azure identity must be federated to this repository and granted the minimum
signing permission on the verified certificate profile. The Windows job builds
an unsigned package, signs it with `azure/artifact-signing-action@v2`, verifies
the trusted signature/timestamp/publisher/hash, and only then uploads it. If
the configuration is absent, the Windows artifact job is skipped and the
release still publishes Python artifacts, checksums, SBOM, provenance, GHCR
images, and release notes. Partial or invalid configuration fails the release;
self-signed and PFX credentials are development/test paths, not production
release evidence.

Before creating an immutable release tag, run the manual
`windows-signed-candidate.yml` workflow with the full 40-character commit SHA
that is already reachable from `main` and the release version. It uses the
protected `production` environment, refuses branch names and unmerged commits,
signs/verifies the exact package, runs install/launch smoke, and uploads
candidate metadata, the public certificate, and SHA-256 record. This workflow
does not create a tag, GitHub Release, container image, or mutable production
state. Use its artifact and run URL as the pre-tag Stage H evidence; the
tag-driven release workflow repeats signing for the immutable tag.

GHCR packages should be kept to immutable semantic tags and active operational
tags. Remove obsolete experimental images only after confirming no deployment,
release note, or rollback record references their digest.

For a production release, fill in
[`docs/PRODUCTION-EVIDENCE.md`](PRODUCTION-EVIDENCE.md) with the exact candidate
SHA, workflow/check URLs, immutable image digest, package checksums, and any
required external staging/production drill evidence. CI evidence must not be
used to claim that an external PostgreSQL HA/PITR, IdP, provider, object store,
vector store, alert route, or production Windows deployment has been exercised.

## Repository cleanup

After merges:

```bash
git fetch --prune origin
git switch main
git pull --ff-only origin main
git branch --merged main
```

Delete local and remote branches that are merged and no longer needed. Keep
only `origin/main` as the default remote branch unless an active release,
hotfix, or incident branch is intentionally open.

## Incident evidence

When GitHub automation is part of an incident or release decision, record:

- pull request or workflow run URL;
- commit SHA and tag, if any;
- relevant check names and conclusions;
- artifact names and checksums;
- package image tag and digest;
- alert number, advisory ID, or CodeQL rule ID when applicable.
