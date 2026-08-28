# Control-plane model lifecycle

`zeaz-control` is an independent package and process with its own credentials
and private SQLite state. Provider adapters own credentials in memory; model
records contain only provider, account, region, public model metadata, source,
and observation time.

Discovery is bounded by page size, page count, total models, cursor length, and
record schema. Repeated cursors and duplicate model IDs abort before any state
write. Once a complete snapshot is available, model upserts, missing-model
observations, lifecycle transitions, and a correlated audit event commit in
one `BEGIN IMMEDIATE` transaction.

A model is not retired after one incomplete provider response. The configured
number of consecutive complete snapshots must omit it first. A reappearing
model is reconciled from provider state and its revision advances. Provider-
specific public fields live under the extension namespace rather than changing
portable semantics.

Public API provenance includes the OpenAI Models API:
<https://platform.openai.com/docs/api-reference/models>.
