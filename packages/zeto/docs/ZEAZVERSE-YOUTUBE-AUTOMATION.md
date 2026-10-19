# ZEAZVERSE — Unified YouTube Automation

Status: **partial implementation / external integration pending**.

Target: [@ZEAZVERSE](https://www.youtube.com/@ZEAZVERSE).

## Single integration boundary

Use `packages/zeto` as the only ZEAZVERSE YouTube publishing surface. Reuse its existing `YouTubePublishingProvider`, publishing service, and platform analytics persistence. A canonical approval repository and its production wiring still need to be implemented; do not imply that this repository already exists. Do not create parallel YouTube clients under `kids-factory`, `zworkforce/` or `services/zc`.

One workflow: `DRAFT → QA → APPROVED_FOR_PRIVATE_UPLOAD → PRIVATE_UPLOADED → PUBLICATION_APPROVAL → PUBLISHED → ANALYTICS_SYNCED`.

## Implementation status

- **Implemented in this branch:** YouTube uploads fail closed unless privacy is `private`; server-side publishing approval verifier is required before any visibility change; regression tests cover those boundaries.
- **Already present:** YouTube adapter validates access tokens against `channels?mine=true`, supports resumable upload, reads basic video statistics/status, and publishes through the Zeto provider registry.
- **Not implemented / blocked:** OAuth 2.0 authorization-code + PKCE lifecycle, encrypted credential refresh/rotation, channel ID binding, durable approval consume-once integration, resilient upload retries/reconciliation, Analytics API reporting, production quota controls, channel setup verification and live provider tests.

## Required OAuth flow

1. Register a Google Cloud OAuth consent screen and authorized redirect URI for the chosen deployment.
2. Request minimum necessary Google scopes and offline access only as needed; use Authorization Code + PKCE, `state`, one-time verifier and short-lived session.
3. Exchange authorization codes server-side. Never send access/refresh tokens to the browser or log them.
   - For `videos.insert` private uploads, Google documents `https://www.googleapis.com/auth/youtube.upload` (among other accepted scopes).
   - For `videos.update` visibility changes, request and verify `https://www.googleapis.com/auth/youtube.force-ssl` or `https://www.googleapis.com/auth/youtube` as appropriate; `youtube.upload` alone is not listed as an accepted scope for that operation.
   - Verify the actual granted scopes at connection and refresh time. Disable visibility-changing features if an accepted scope was not granted. Never silently elevate scope or reuse an upload-only grant.
   - Official references: https://developers.google.com/youtube/v3/docs/videos/insert and https://developers.google.com/youtube/v3/docs/videos/update.
4. Encrypt refresh tokens via the existing server-side secret infrastructure. Support token rotation and revocation.
5. Bind the token to the exact YouTube channel ID returned by `channels.list(mine=true)`, not just a mutable handle.
6. Validate that the connected channel is the operator-approved `@ZEAZVERSE` channel before any upload.

### Verify an operator-provided OAuth grant

The OAuth lifecycle is not implemented by this package yet. Before enabling a visibility-changing integration, an operator can verify the actual granted scope on the intended YouTube account with the opt-in integration test below. The access token is sent only in the HTTPS POST body to Google's tokeninfo endpoint; the test does not print the token or scope values. Run it against the same grant configured for the integration and rotate/revoke the test token afterward according to the operator's credential policy.

```bash
cd packages/zeto
export YOUTUBE_OAUTH_TEST_ACCESS_TOKEN='operator-provided-access-token'
ZETO_REQUIRE_YOUTUBE_SCOPE_TEST=1 node --test test/youtubeOAuthScope.integration.test.js
unset YOUTUBE_OAUTH_TEST_ACCESS_TOKEN
```

Without `YOUTUBE_OAUTH_TEST_ACCESS_TOKEN`, the test is skipped by the normal package test suite. The forced command fails when the token is missing. This check verifies the granted OAuth scope only; it does not upload or modify a YouTube video and does not replace a separately authorized live publishing test.

## Private-first upload

- `videos.insert` always sets `status.privacyStatus=private`.
- Validate content format, size, MIME type, rights, made-for-kids selection, and synthetic media disclosure prior to upload; both audience/disclosure flags are explicit booleans and travel in the insert `status` body.
- Visibility approval carries the reviewed resource `expectedEtag`; a changed ETag invalidates the approval before any mutation.
- Use resumable upload with a durable session reference and status reconciliation, including uncertain network failures.
- Store the provider video ID, content hash, channel ID, idempotency key, source artifact and trace IDs.
- Do not retry after an ambiguous result without checking for already-created video.

## Independent publication approval

- Upload approval and public-visibility approval are distinct.
- Implement canonical Zeto approval persistence with RBAC, tenant/channel scoping, immutable video/content/metadata digest, expiry, distinct human reviewer and consume-once action.
- Implement and inject `verifyPublicationApproval` from a trusted server-side service backed by durable approval persistence, RBAC, tenant/channel scoping and an atomic consume-once claim. This repository currently has only the provider callback boundary; it has no canonical approval repository or production wiring.
- Only `finalizePublicationApproval`, invoked after the provider reconciles the new visibility from YouTube, consumes the approval exactly once with an immutable audit event; it must be idempotent so a retried confirmation cannot double-consume.
- If YouTube reports a changed ETag, matching visibility alone is not proof that this approval caused the transition. The provider fails closed and does not finalize; an operator or future durable claim integration must reconcile the uncertain outcome.
- Adapter explicitly **rejects** public/unlisted transitions if no verifier is configured.
- Verify YouTube's resulting status and record an immutable audit event.
- No scheduler or agent may bypass human approval.

## Analytics

- Basic publicly exposed counters from `videos.list(part=statistics)` are not a substitute for YouTube Analytics.
- Add OAuth-authorized YouTube Analytics API reports with explicit dimensions/metrics, channel and date range.
- Persist observed counts, timestamps and provenance; label missing/unauthorized analytics as unavailable.
- Incremental synchronization, quota budgets, retries with backoff, and a dashboard with no invented metrics.

## Verification gates

1. Unit: non-private upload rejected before HTTP request.
2. Unit: upload metadata is always private.
3. Unit: visibility action fails without valid canonical approval.
4. Unit: valid verifier enables only the approved video/visibility.
5. Integration: OAuth state/PKCE, token encryption/refresh, channel binding, idempotent resumable upload.
6. Integration: replayed approvals, expired approvals, wrong channel, wrong actor, tenant mismatch, provider 401/403/429 and network timeout.
7. Mock analytics provenance and empty-state tests.
8. Operator-owned evidence: valid Google consent configuration, real `@ZEAZVERSE` channel ID, private upload and status confirmation, human-approved public transition, real analytics receipt.

Run `cd packages/zeto && npm ci && npm run check`. Keep all actual results in the PR; do not claim checks passed unless they executed.

## Rollback

Keep initial publication visibility private. Disable the Zeto YouTube integration and revoke the Google OAuth grant if compromised. Reverting code must not assume it can reverse a previously public video; use separately approved YouTube changes to restore privacy.

## Operator actions

Google OAuth consent screen/credentials, redirect URL verification, channel approval, and live provider execution require authorized operator participation. Never commit secrets.
