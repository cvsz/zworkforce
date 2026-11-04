# Public Submodule Checkout Policy

**Status:** Public HTTPS checkout; no long-lived submodule SSH credentials are required.

## Scope

The CI workflow checks out these public, commit-pinned submodules:

- `cvsz/zksato`
- `cvsz/zttshop-php`
- `cvsz/zmovie`
- `cvsz/zok`

## Security controls

- Every `.gitmodules` URL uses an explicit HTTPS remote.
- CI uses anonymous HTTPS submodule fetches and does not receive repository deploy keys.
- The parent repository checkout keeps `persist-credentials: false`.
- CI verifies each checked-out submodule HEAD against the gitlink SHA recorded in the parent commit.
- Fork and Dependabot pull requests cannot modify `.gitmodules` or the four submodule gitlinks.
- Submodule code execution remains restricted to the existing trusted-event condition; public source retrieval itself requires no credential.

Do not add a long-lived SSH deploy key to a `pull_request` workflow. If a future submodule becomes private, fail the checkout closed and design a separately reviewed, short-lived, read-only GitHub App credential flow. Do not silently restore the current secret-bearing workflow.

## Validation

Run the focused policy tests:

```bash
python3 -m unittest tests.test_submodule_security -v
```

Run the repository-required validation before merge:

```bash
python3 -m compileall -q zworkforce tests scripts
PYTHONPATH=. python3 -m unittest discover -s tests -v
zworkforce doctor
```

## Rollback

Revert the HTTPS URL and CI workflow change only if the public repositories are no longer anonymously fetchable. Do not restore long-lived deploy keys in PR-triggered workflows. Keep submodule validation fail-closed until a separately reviewed, short-lived, read-only credential design is available.
