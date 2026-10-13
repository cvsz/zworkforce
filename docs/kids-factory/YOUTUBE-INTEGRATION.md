# YouTube Integration

Slice uses `youtube_mock` only. Contract enforced:

- Metadata: title/description/tags/category/language/thumbnail/playlist/visibility/audience/schedule/rights/synthetic disclosure.
- Audience classification is explicit; `madeForKids=false` is never hardcoded.
- OAuth/token storage, refresh, scopes, upload, status, analytics via real Data API are PENDING EXTERNAL EVIDENCE.
- Idempotency key -> stable mock external id prevents duplicate uploads on retry.
- Human approval row is mandatory; `kids_publish_approved` fails closed otherwise.
- View counts are never fabricated; analytics snapshots set `synthetic=1`.
