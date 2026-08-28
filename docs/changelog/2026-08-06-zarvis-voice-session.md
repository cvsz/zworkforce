# Z.A.R.V.I.S. realtime voice and durable session slice

- Connected finalized ZVoice transcripts to the owner-only Z.A.R.V.I.S. command contract.
- Added append-only session events, durable file-backed command results, and idempotent replay/conflict handling.
- Added owner-only session history and explicit confirmation-gated deletion.
- Added the `zarvis.session.event.v1` schema, updated completion replay metadata, runbooks, feature matrix, and 21 focused passing tests.

This fragment is referenced by PR validation and should be folded into the root `CHANGELOG.md` during the next release consolidation.
