# zc web workspace

The supported browser workspace is a React/TypeScript static application
served by `app.main:app`. It uses only the tenant-aware `/v1` API and never
receives provider credentials.

## Runtime

Start one process:

```bash
zc --host 127.0.0.1 --port 8000 --workers 1
```

Open `http://127.0.0.1:8000/`.

The production bundle is committed under `frontend-dist/` and included in the
Python wheel and container image. Node.js is not required at runtime.

## Frontend development

```bash
cd webapp/frontend-src
npm ci
npm test
npm run build
```

`npm run dev` starts Vite on `127.0.0.1` and proxies `/v1` and `/ready` to the
zc API on port 8000.

## Data and credentials

- Conversations are tenant-scoped and persisted as permission-restricted
  atomic JSON documents under `data/chat/sessions/`.
- Drafts and response preferences use browser IndexedDB.
- The optional application bearer token is held in memory only.
- Anthropic, OpenAI, and other provider credentials remain server-side.
- The frontend has no analytics, cloud sync, ShareGPT, Upstash, or WebDAV
  integration.

## Legacy adapter

`backend/server.py` and the dependency-free files under `frontend/` remain
only as a compatibility surface while downstream users migrate. They are not
started by either standalone Compose profile.

## Attribution

The interaction design is informed by NextChat. Any source incorporated from
NextChat must retain its MIT license notice. The current implementation uses
zc-owned components and does not include NextChat provider proxies or cloud
features.
