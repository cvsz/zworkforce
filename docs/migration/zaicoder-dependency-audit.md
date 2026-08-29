# ZAI Coder Dependency Audit

Source: `cvsz/zeaz-platform/apps/zaicoder`

## Selected migration boundary

| Legacy component | Z Platform target | Decision |
|---|---|---|
| Python CLI backend | `apps/zaicoder/backend` | Retain, replace direct provider credentials with gateway token |
| Browser terminal | `apps/zaicoder/web` | Retain after server-route and auth audit |
| File upload UI/API | application layer | Retain with size/type checks and temporary-file cleanup |
| Remote MCP support | AI Gateway policy | Allow only HTTPS servers and explicit tool allowlists |
| Admin, compliance and WIF operations | separate privileged adapters | Do not expose through ordinary user sessions |

## Required gates before importing runtime code

1. Inventory imports and pinned dependencies.
2. Replace direct provider API keys in browser or CLI configuration.
3. Preserve the streaming final-render regression test.
4. Run unit tests, secret scan, lint, and dependency audit.
5. Record service account scopes and rollback instructions.

## Source provenance

The source baseline is the ZAI Coder component in `cvsz/zeaz-platform`. New platform code must not copy environment values, deployment identifiers, or credentials from the legacy repository.
