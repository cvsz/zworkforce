# ADR-001: Define Product Surface Boundaries

- **Status**: accepted
- **Date**: 2026-07-20
- **Deciders**: repository maintainers
- **Tags**: architecture, packaging, compatibility

## Context

The repository contains four overlapping trees: `app/`, `src/wire/`,
`webapp/`, and agent configuration under `.agents/` and `.zc/`. They evolved
at different times and previously had no enforceable ownership or dependency
direction. This made living documentation, packaging, security gates, and
release claims ambiguous.

The public-local deployment contract requires a supported FastAPI origin on
loopback. Existing users also depend on the `zc` command and its legacy feature
modules. The web console currently adapts the legacy CLI domain, while agent
configuration is development tooling and must not enter the runtime package.

## Decision

The product surfaces are classified as follows:

| Surface | Classification | Runtime role | Support contract |
|---|---|---|---|
| `app/` | supported core | FastAPI, local gRPC, storage, authorization | Primary public-local runtime |
| `src/wire/` | compatibility | Installed `zc`/`zcoder` CLI and API client | Maintenance support; new server behavior belongs in `app/` |
| `webapp/` | optional adapter | Local control panel over compatibility services | Supported when explicitly enabled |
| `.agents/`, `.zc/` | development tooling | Agent instructions, skills, and local automation | Excluded from runtime packaging |

Dependencies flow in one direction:

```text
webapp (optional adapter) -> wire (compatibility)

app (supported core)      independent
wire (compatibility)      independent
agent tooling             build/development only
```

The following rules are enforced:

1. `app/` must not import `wire` or `webapp`.
2. `src/wire/` must not import `app` or `webapp`.
3. `webapp/` may import `wire` while it remains the compatibility adapter, but
   it must not become a dependency of `app/`.
4. Runtime packages are enumerated explicitly in `setup.cfg`; agent tooling is
   never included.
5. `zc` and `zcoder` remain compatibility CLI commands. `zc-api` is the
   supported API server command.
6. New public endpoints, authentication, storage, and network behavior belong
   in `app/`. New CLI behavior should call the API rather than duplicate server
   state.

## Consequences

### Positive

- Security and quality claims have a precise supported boundary.
- The API can evolve without importing the legacy CLI implementation.
- Compatibility remains available without treating every historical module as
  part of the public server.
- Packaging and CI can detect accidental cross-surface coupling.

### Negative

- The distribution still ships more than one product surface during the
  compatibility period.
- The web console retains a dependency on `wire` until its API-client migration
  is complete.
- Changes shared by the API and CLI may require a neutral package in a future
  ADR rather than a direct cross-import.

### Neutral

- Historical documents keep their point-in-time meaning.
- Existing `/v1/wire` HTTP routes remain for backward compatibility.
- This decision classifies current surfaces; it does not remove compatibility
  commands.

## Migration gates

The compatibility period ends only after:

1. every specialized CLI operation has an authorized API equivalent;
2. the web console uses the API client instead of importing `wire`;
3. deprecation is documented for at least one release;
4. package-install, API, CLI, and migration tests pass; and
5. a follow-up ADR approves removal or separate distribution of `wire`.

## Links

- [Repository audit](../REPOSITORY_AUDIT_2026-07-20.md)
- [Architecture](../../ARCHITECTURE.md)
- [Repository instructions](../../AGENTS.md)
