---
name: zworkforce-conventions
description: Repository-specific development conventions for the zWorkforce Python service, Windows client, and packages/zarvis workspace.
---

# zWorkforce conventions

Use this skill when changing this repository. Verify the relevant package's own
instructions before editing because this is a polyglot monorepo.

## Repository layout

- `zworkforce/`: Python 3.11+ service and CLI.
- `tests/`: Python `unittest` suite.
- `ZWorkforceClient/`: .NET Windows client and its tests.
- `packages/zarvis/`: independently packaged Z.A.R.V.I.S. workspace; follow its
  nested `AGENTS.md` and package scripts.
- `docs/`, `examples/`, and `scripts/`: operational documentation, examples,
  and release/backup helpers.

## Python conventions

- Use `snake_case` for modules, functions, methods, and variables;
  `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants.
- Prefer standard-library facilities unless a dependency is justified in
  `pyproject.toml`.
- Keep tenant, authorization, secret-handling, SSRF, and audit boundaries
  intact. Never log credentials or expose provider secrets to static assets.
- Match the existing type-annotation style and keep public behavior covered by
  tests in `tests/`.

## Validation

Run the narrowest relevant test first, then the repository checks before
publishing a change:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q zworkforce tests
```

For Windows-client changes, use the solution and pinned SDK under
`ZWorkforceClient/`. For Z.A.R.V.I.S. changes, use the package-manager commands
documented under `packages/zarvis/`. GitHub Actions is the final authority for
platform-specific checks.

## Commits and pull requests

- Use concise Conventional Commit subjects such as `feat:`, `fix:`, `docs:`,
  `test:`, or `chore:`.
- Keep changes scoped, add regression coverage for fixes, and update operational
  documentation when configuration or deployment behavior changes.
- Do not commit credentials, local environment files, generated build output,
  or user-specific MCP configuration.
