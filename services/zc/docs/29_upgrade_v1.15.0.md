# v1.15.0 upgrade notes — ROADMAP.md gap-audit implementation

This release implements the five buildable gaps from `ROADMAP.md` Part 2.
Nothing here changes default behavior — every new capability is opt-in via
a new flag.

## P0 — Server-side `fallbacks` param

`zc_fable5.py`'s `Fable5Client` already had a client-side manual
fallback (`call_with_fallback()`: on a refusal, make a second HTTP call to
`self.fallback_model`). That's a real, documented pattern, but it costs an
extra round trip. The `fallbacks` request parameter lets the platform do
the same retry server-side, in the same round trip:

```bash
ai-coder --fable5 "risky prompt" \
  --fable5-fallback-chain zc-opus-4-8
```

`call_with_fallback()` now branches on whether `fallback_chain` is set:
if so, it just reads back which model in the chain answered; if not, it
falls through to the original manual retry path unchanged.

## P1 — Context editing in the agent loop

The roadmap's audit claimed `context_management`/`clear_tool_uses`
appeared nowhere in the codebase. That was wrong: `zc_tools.py`
already has a complete `build_context_management()` (clear_tool_uses,
clear_thinking, and compact edit types, with the right beta headers). The
real gap, found while implementing this, was narrower: `zc_code.py`'s
`--code-agent` loop never called it.

```bash
ai-coder --code-agent -p "long multi-file refactor" \
  --agent-context-editing
```

This is complementary to the existing Compaction support in the same
loop: Compaction *summarizes* the conversation once it nears the context
limit; `clear_tool_uses` *drops* stale tool_result content once the
conversation crosses a smaller token trigger, keeping the most recent N
tool uses intact. Using both together on a long `--code-agent` session
means most of the pruning happens cheaply via clearing, well before
Compaction's summarization would ever need to kick in — worked example:

```python
from zc_code import CodeAgent, CodeSession
from zc_tools import build_context_management

agent = CodeAgent(api_key=key, model="zc-sonnet-5")
session = CodeSession(cwd=".", model="zc-sonnet-5")

cm = build_context_management(
    clear_tool_uses=True, clear_tool_uses_trigger_tokens=30000,
    compact=True, compact_trigger_tokens=150000,
)
result = agent.query(prompt="...", session=session, context_management=cm)
```

## P1 — Agent Skills API (`skill_id`)

New module `zc_skills_api.py`. This is a *different* feature from
`zc_code.py`'s `SkillsRegistry`, which reads
`.zc/skills/<name>/SKILL.md` off the caller's local filesystem. The
platform Skills API instead references pre-built or custom skills by
`skill_id` inside a Messages request's code-execution container:

```bash
ai-coder --skills-list
ai-coder --skills-info pptx
```

```python
from zc_skills_api import SkillsApiClient

client = SkillsApiClient(api_key=key)
data = client.call_with_skills(
    "Build a 5-slide deck summarizing this data.",
    skills=["pptx"],
)
```

Routing `zc_excel.py` / `zc_powerpoint.py` through this instead of
their existing hand-rolled pandas/openpyxl and python-pptx implementation
is a deliberate follow-up (`--excel-native` / `--pptx-native`), not part
of this release — the current implementation keeps working as-is and as
the fallback for accounts without Skills access.

## P2 — Usage and Cost API + API key management

New module `zc_admin_api.py`, combining both since they share the
same Admin API key requirement:

```bash
ai-coder --usage-report --admin-api-key sk-ant-admin-...
ai-coder --admin-list-keys --admin-api-key sk-ant-admin-...
ai-coder --admin-revoke-key key_abc123 --admin-api-key sk-ant-admin-...
```

`--admin-create-key` does not call an endpoint — ZaiCoder doesn't
document one. API keys are created through the Console UI, where the
secret is shown exactly once; that's a deliberate security boundary, not
a documentation gap, so this flag explains that instead of faking a
response or silently failing.

`zc_cost_optimizer.py` is unchanged and still does local, estimate
-based cost tracking from token counts — useful for routing decisions
inside a single CLI session. `--usage-report` is the real, org-level,
historical number ZaiCoder actually bills against; the two are
cross-linked in each module's docstring.

## P2 — Compliance API

Left as a documented gap. Per the roadmap's own recommendation, this is
an enterprise compliance/audit-log surface with no concrete use case for
a personal/small-team coding CLI yet — building against a guessed shape
risks building the wrong thing. Revisit only on an actual request.
