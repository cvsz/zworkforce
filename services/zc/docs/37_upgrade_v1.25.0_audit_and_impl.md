# v1.25.0 audit cycle — gap findings + implementation notes

Continuation of the cross-product cycle (v1.24.0 committed to re-running
the full `platform.zc.com/docs/en/release-notes/overview` sweep and
following up on the deferred `zc_models.py`/`requirements.txt` drift
check). Model catalog checked first — no new model releases since
zAICoder Sonnet 5 (June 30, 2026); `MODEL_CATALOG` in `zc_models.py`
is current. Two further gaps found while re-reading the same release
notes page this cycle started from.

## Finding 1 — Extended thinking `display: "omitted"` (GA, no beta header)

**What it is:** A `thinking.display` field — set it to `"omitted"` to
receive thinking blocks with an empty `thinking` field but the
`signature` preserved for multi-turn continuity, letting a client skip
receiving/streaming thinking content it doesn't render anyway, for
faster streaming. Billing is unchanged (thinking tokens are still
generated and billed; only the response payload is thinner).

**Why it's a gap:** `zc_thinking.py`'s thinking config builders only
ever produce `{"type": "enabled", "budget_tokens": ...}` — first grep
for `display` in the file (as a `thinking` sub-field, not the CLI
"Thinking display (show/hide/summary)" client-side feature mentioned in
the module's own docstring, which is a different, older, purely local
concept — hiding already-received thinking text from stdout, not asking
the server to omit it): zero matches for the server-side field.

**Priority: 🟠 P1.** Direct latency/bandwidth win for any
`--stream`-style caller that doesn't render thinking text — exactly the
kind of caller `zc_thinking.py` already serves.

## Finding 2 — CMEK `external_keys` Admin API endpoints

**What it is:** On zAICoder Platform (not zAICoder Platform on AWS, where
this surface is explicitly unavailable per the docs), customer-managed
encryption keys are "configured with the Admin API" — the docs
reference "the `external_keys` API endpoints" by name when noting
they're unavailable on the AWS variant, confirming they exist as a
distinct Admin API surface on standard zAICoder Platform, alongside the
Console UI path.

**Why it's a gap:** First grep for `cmek`/`external_keys`/`CMEK` across
the whole tree: zero matches anywhere, including `zc_admin_api.py`
and `zc_compliance_api.py`.

**Confirmation needed before shipping:** unlike every other finding in
the last several cycles, I was not able to find (or safely fetch) the
`external_keys` endpoint's exact path, request body shape, or response
schema in this session — only that it exists and is Admin-API-scoped.
The implementation below is written defensively (a thin, generic
`_post`/`_get` pass-through matching this file's existing `_get()`
helper pattern) specifically so the *shape* can be corrected later
without changing the public method signatures, but the exact path
segments (`/organizations/external_keys` is a reasonable guess by
analogy with every other Admin API resource in this file being nested
under `/organizations/...`, not a confirmed one) must be checked against
the live API reference before this is used against production.

**Priority: 🟡 P2 (implemented defensively, needs a follow-up
verification pass — see note above)**. CMEK is an eligibility-gated,
contact-your-account-team feature to begin with, so real-world usage of
this code path is inherently rare; shipping a reasonable-best-effort
client now, clearly flagged, is better than leaving the surface
completely unaddressed for another cycle.

## Non-gap checked this cycle

**`cmek_preserve` Compliance API activity events** (new event type,
plus two new preservation reason codes `policy_violation_investigation`
and `csae_report`) — confirmed **not** a gap:
`zc_compliance_api.py`'s `list_activities()`/`iterate_activities()`
already take `activity_types` as a free-form list with no hardcoded
enum anywhere in the file, so new event type strings — this one
included — work today with zero code changes, exactly like the
"broader webhook coverage" non-gap noted in the v1.21.0 cycle.

**`stop_details.category: "reasoning_extraction"` on Fable 5** and the
server-side **`fallbacks` param** — both already fully implemented in
`zc_fable5.py` (checked directly rather than assumed, since both
looked like plausible new gaps from the release notes wording alone).

**Mid-conversation `role: "system"` messages after a user turn on Opus
4.8** — already implemented in `zc_cache.py` (v1.18.0).
