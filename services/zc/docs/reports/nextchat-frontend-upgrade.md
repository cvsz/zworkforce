# NextChat-Informed Frontend Upgrade

Date: 2026-07-20

## Reference

The interaction audit used ChatGPTNextWeb/NextChat at commit
`706a18b95b714ab29b2a4842d3b9ff4f887935d5`. NextChat is MIT licensed.
No provider adapter, cloud synchronization, analytics, marketplace, or
desktop-runtime code was incorporated.

## Decision

zc adopts the useful interaction patterns without embedding the Next.js
application:

- responsive conversation sidebar;
- searchable durable sessions;
- streaming response display and cancellation;
- Markdown rendering and conversation export;
- model, agent, personality, and skill discovery;
- in-memory application bearer token handling;
- IndexedDB-backed drafts and response preferences.

The supported frontend is a React/TypeScript static build. FastAPI serves it
from the same origin and process as the tenant-aware API and embedded LiteLLM
Router. Node.js is a build-time dependency only.

## Explicit Exclusions

- browser-managed provider API keys;
- Next.js provider proxy routes;
- ShareGPT or other third-party conversation uploads;
- Upstash, WebDAV, hosted analytics, and remote synchronization;
- the NextChat MCP marketplace;
- Tauri and desktop packaging;
- a separate frontend runtime process.

## Runtime Contract

```text
Browser
  -> FastAPI static frontend
  -> /v1/chat/sessions
  -> /v1/chat/sessions/{id}/responses (SSE)
  -> AIService
  -> embedded LiteLLM Router or direct server-side provider
```

Chat sessions are tenant-namespaced atomic JSON documents with `0700`
directories, `0600` files, atomic replacement, final directory `fsync`, opaque
identifiers, and no-follow reads. Provider credentials never cross the server
boundary.

## Verification

- React typecheck and production build;
- Vitest API/SSE fragmentation tests;
- Python API, tenant-isolation, restart, traversal, symlink, and corruption
  tests;
- desktop and mobile headless Chromium smoke rendering;
- non-root Docker image smoke test;
- container restart persistence test with a local volume;
- wheel content and console-entry-point inspection;
- Ruff, Bandit, compileall, pytest, npm audit, gitleaks, and diff checks.
