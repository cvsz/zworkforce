# v1.18.0 upgrade notes — Mid-conversation system messages + Cache diagnostics CLI wiring

This release comes from re-running `ROADMAP.md`'s own gap-audit
methodology against the live docs at platform.zc.com/docs. The
previous audit was dated 2026-07-04; this one is dated 2026-07-08. Two
real findings, both closed here — plus a correction to `ROADMAP.md`
itself, which had drifted from what was actually true in the codebase.

## Finding 1 — Mid-conversation system messages (new, genuinely missing)

**What it is:** on Opus 4.8, you can append a `{"role": "system", ...}`
message into the middle of `messages` to update zAICoder's instructions
partway through a conversation — no beta header required. The key
property: unlike editing the top-level `system` field, this doesn't
touch the hashed system/tools prefix that prompt caching keys off of, so
an existing cache entry still matches and only the new message is
processed as fresh input. It's the caching-aware way to say "change your
behavior from here on" in a long-running conversation.

**Why it's not the same as `--cache-system`:** `--cache-system` sets the
top-level `system` field — right for instructions that apply from turn
one. A mid-conversation system message is for instructions that only
become relevant later, without invalidating everything cached before it.

**What was built**, all in `zc_cache.py`:

- `build_mid_system_message(text)` — builds the message block. Content is
  text-only (no images, documents, tool blocks, or citations, per docs).
- `validate_system_message_placement(messages)` — encodes all five
  documented placement rules and raises `SystemMessagePlacementError`
  naming the specific one that failed, rather than a generic error:
  - Cannot be the first entry in `messages`.
  - Cannot be adjacent to another system message.
  - Must immediately follow a user turn, or an assistant turn ending in a
    *server* tool use (a client-side `tool_use` doesn't qualify — it's
    always followed by its own `tool_result`, so a system message there
    would split them, which is separately disallowed).
  - Cannot sit between a `tool_use` block and its `tool_result`.
  - Must be the last entry in `messages`, or be followed by an assistant
    turn.

  Validation runs client-side before the request goes out, so a
  misplaced system message fails fast with a specific message instead of
  spending a round trip on the API's 400.

- `MID_SYSTEM_SUPPORTED_MODELS = {"zc-opus-4-8"}` — a model gate.
  Everything else raises `ValueError` pointing at `--cache-system`
  instead.
- `mid_system` param on `generate_cached()`, `mid_system_updates`
  (`{turn_index: text}`) param on `multi_turn_cached()`. The multi-turn
  version is the realistic use case: the placement rules require an
  existing user turn to attach to, so a single-shot call with no history
  can't legally carry one — this is a property of the feature itself,
  not a limitation of this implementation.

```bash
python main.py --cache --cache-multi-turn "First question" "Follow-up question" \
    --cache-mid-system "From now on, answer in bullet points." \
    --cache-mid-system-after 0 --model zc-opus-4-8
```

Security note carried through from the general operator-authority
rules already documented elsewhere in this codebase: a mid-conversation
system message has the same authority as the top-level `system` field.
Never build one from untrusted content (tool output, retrieved
documents, web content, user-supplied text) — that would grant that
content operator-level instructions. `build_mid_system_message()`'s
docstring says this explicitly.

## Finding 2 — Cache diagnostics (beta): the gap was narrower than it looked

The audit's first pass — grepping for `cache_diagnostic` /
`cache.diagnostic` — found nothing and looked exactly like Finding 1: a
fresh, real gap. It wasn't. Reading `zc_cache.py` directly (per the
"confirm with a second, differently-worded grep" correction this cycle
added to the Methodology note) turned up a fully-built feature: the
`diagnose=` parameter on `generate_cached()`, the
`cache-diagnosis-2026-04-07` beta header, the request-side
`diagnostics.previous_message_id` field, and `cache_miss_reason` already
surfaced through `cache_stats()` / `print_cache_stats()`. None of the
grep patterns matched because the actual identifiers just don't contain
the substring `diagnostic`.

The real gap: nothing in `main.py` ever set `diagnose=True`. The feature
existed but had no way to be reached from the CLI. Fixed with one flag:

```bash
python main.py --cache -p "..." --cache-diagnose
```

This is a one-line, narrow finding — logged as its own item rather than
folded silently into Finding 1, because "the audit's initial signal was
wrong and the real fix was much smaller" is itself worth recording, the
same way the v1.15.0 cycle recorded that "context editing" turned out to
already have a `build_context_management()` helper waiting to be wired
up rather than built from scratch.

## Drift check

This cycle's methodology also explicitly checks for drift, not just
net-new features. `zc_models.py`'s model catalog (Fable 5, Mythos 5,
Opus 4.8, Sonnet 5, Haiku 4.5, and the legacy tiers) was compared against
the live Models overview and found to match exactly — no stale entries,
no missing releases, no `requirements.txt` version drift. Nothing to fix
here this cycle.

## `ROADMAP.md` itself was stale

Independent of the two findings above: `ROADMAP.md`'s header still read
"v1.15.0" and its audit date was frozen at 2026-07-04, four days behind
where the codebase actually was. More substantively, four of the six
gaps closed back in the v1.15.0/v1.16.0 cycles (`fallbacks`, context
editing, the Skills API, and Usage/Cost + API key management) were never
marked done in Part 2 or the Priority Summary — only the Compliance API
entry had been updated. `IMPLEMENTATION_CHECKLIST.md` and `CHECKLIST.md`
had the accurate status the whole time; `ROADMAP.md`'s Part 2 prose just
never got the follow-up edit. Corrected as part of this cycle: every
closed item now says so in `ROADMAP.md` itself, not just in the
checklists, and the header/audit-date now read v1.18.0 / 2026-07-08.

## Tests

`zc_cache.py` had zero test coverage before this release —
surprising given every other module in the tree has a matching
`tests/test_zc_*.py`. Added `tests/test_zc_cache.py`, 18 tests
covering: basic cache-breakpoint behavior (pre-existing), the `diagnose=`
request shape on both the first call (`previous_message_id: None`) and a
follow-up call (references the prior message ID, surfaces
`cache_miss_reason`), the beta header, `build_mid_system_message()`'s
shape, every placement rule in `validate_system_message_placement()`
(both the valid and invalid cases), and the model gate on both
`generate_cached()` and `multi_turn_cached()`. All 150 tests in the repo
pass (132 pre-existing + 18 new).
