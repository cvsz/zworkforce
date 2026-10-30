# ZChat

ZChat is the platform chat surface migrated from `cvsz/z-platform/apps/zchat`.
Its public hostname is `zcoder.zeaz.dev`; `zchat.zeaz.dev` is reserved for the ZChat Control Server.

This version keeps the browser UI thin and routes model calls through the platform AI Gateway. Browser code must never contain upstream provider keys, direct provider base URLs, or tenant-wide service credentials. The interface uses a familiar conversation-list and message-thread layout; it is an independent ZChat AI client and does not connect to Facebook Messenger.

The current shell renders a transcript and browser-local conversation history. Conversation title, system prompt, prompt templates, import/export, and theme controls are grouped behind conversation options. Assistant replies stream through the gateway when supported and use a safe Markdown subset for headings, lists, quotes, code fences, inline code, and HTTP(S) links.
The composer also exposes a stop action that aborts the active generation without exposing provider credentials or bypassing the gateway path.

## Runtime

- `GET /health` reports service status, gateway configuration, and session TTL.
- `GET /api/models` loads the AI Gateway model catalog for the browser model selector.
- `POST /api/chat` accepts `{ "prompt": "...", "model": "optional", "conversation_id": "optional", "system_prompt": "optional" }` and forwards an OpenAI-compatible request to the AI Gateway.
- `POST /api/chat/stream` forwards streaming chat requests, including the pinned system prompt, and returns server-sent events from the AI Gateway.
- `POST /api/logout` clears browser storage via `Clear-Site-Data`; it does not sign out of an external identity provider.
- `GET /` serves the accessible chat shell with transcript, history sidebar, conversation options, prompt templates, export controls, theme toggle, composer with stop/send controls, model picker, new chat, retry, and clear controls.

Chat completion requests use the server-configured tenant plus conversation, request, and usage-correlation metadata. The browser cannot select a tenant. Provider credentials remain server-side in the AI Gateway.

## Required environment

- `Z_PLATFORM_AI_GATEWAY_URL`: AI Gateway base URL. Both `http://gateway:8400` and `http://gateway:8400/v1` are accepted.
- `Z_PLATFORM_SERVICE_TOKEN`: service token used only by this server-side proxy.
- `ZCHAT_TENANT_ID`: trusted server-side tenant context required for chat requests. The browser's `X-Tenant-ID` header is ignored; bind this single-tenant app to the tenant authorized by its deployment identity layer.
- `PHASE6_API_URL` and `ZC_API_URL`: internal backend URLs used by the unified platform status facade.
- `PHASE6_API_TOKEN` and `ZC_API_TOKEN`: optional server-side backend credentials; never expose them to the browser.

The production zc deployment requires `ZC_API_TOKEN`; liveness and readiness probes remain unauthenticated, while upload and wire operations require `Authorization: Bearer <ZC_API_TOKEN>`.
- `ZCHAT_SESSION_TTL_SECONDS` optional. When set, requests with expired `X-Session-Started-At` are rejected.
- `HOST` optional, defaults to `127.0.0.1`.
- `PORT` optional, defaults to `3021`.

## Validation

Run `npm test` in this directory to check health, gateway-only chat forwarding, model catalog loading, streaming forwarding, tenant scoping, conversation IDs, usage correlation, session expiry, logout, browser storage persistence, conversation history navigation, manual conversation titles, pinned system prompts, prompt template persistence, export formatting, theme persistence, stream parsing, stream cancellation, safe markdown rendering, and gateway URL normalization.

## Migration limits

The UI is platform-owned. Production deployments still need the selected platform identity/session provider and end-to-end accessibility/mobile QA in the deployed environment. The configured tenant ID is not user authentication; protect the service with the platform identity layer before public deployment. Meta Messenger integration would require a separate, explicitly configured provider and is not implemented here.
