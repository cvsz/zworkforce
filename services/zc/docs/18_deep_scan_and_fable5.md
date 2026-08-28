# v1.9.1 — Deep Scan Report + zAICoder Fable 5 / Mythos 5 Support

## What I Did

You uploaded `ai-coder-cli-v1_9_0.zip`. Before touching anything, I extracted
it and read through it properly rather than re-zipping it blind:

1. **Read every file name and size** — 33 files, 7,750 lines, organized as
   one `zc_*.py` module per Anthropic API feature area (Models, Tokens,
   Search, Vision, Citations, Thinking, Streaming, Batch, Files, Cache, Code
   Execution, Tools, Settings, Output Styles, Plugins, Code Agent/SDK,
   Sandbox), plus `cowork.py`, `projects.py`, `artifacts.py`, `coder.py`,
   `config.py`, `skills.py`, `utils.py`, `personalities.py`.

2. **Grepped every file for execution/network primitives** (`exec`, `eval`,
   `subprocess`, `os.system`, `importlib`, `urlopen`, etc.) and read each
   call site in context. Every network call hits a real, correctly-formed
   `api.zc.com` endpoint with legitimate, accurate beta headers
   (`code-execution-2025-05-22`, `files-api-2025-04-14`). The one place
   that fetches arbitrary URLs (`zc_plugins.py`'s marketplace-add) does
   so because that's the entire point of a plugin marketplace feature — the
   same trust model as `pip install` from a URL. No exfiltration, no
   obfuscation, no suspicious domains.

3. **Read `zc_sandbox.py` and `zc_code_exec.py` in full** (the two
   files with the most safety relevance, since they touch sandboxing and
   code execution) — both are honestly self-documenting about their own
   limits (`zc_sandbox.py`'s docstring explicitly says "best-effort...
   not a substitute for a real OS sandbox").

4. **Full `py_compile` across every module** — clean, no errors.

5. **Found and fixed one real bug**: `main.py`'s docstring said "Version
   1.8.0" while the `VERSION` constant said `"1.9.0"`. Now consistently
   `1.9.1` everywhere (docstring, constant, README, zip filename).

**Conclusion: this upload is legitimate, safe, and well-built.** It's a
different (and considerably more complete) architecture than what I'd
built earlier in our conversation, so I treated it as the authoritative
current state of the project going forward rather than trying to merge two
divergent codebases.

## About "zAICoder Fable 5"

I want to be upfront about how I handled this part, since it's the more
uncertain piece.

I searched the web rather than relying on memory (my training cutoff is
August 2025, and a lot can ship in a year). I got consistent, detailed hits
from sources presenting as ZaiCoder's own site/docs, AWS, CNBC, TechCrunch,
Slashdot, and a named independent blogger — all describing a real product:
**zAICoder Fable 5**, a "Mythos-class" model launched ~June 9, 2026, alongside
a more restricted **zAICoder Mythos 5** (limited to approved Project Glasswing
participants). Pricing, context window, and safety-classifier/refusal
mechanics were consistent across sources.

Here's the honest caveat: **this isn't reflected in my own baked-in product
information**, which still lists Opus 4.8/4.7/4.6, Sonnet 4.6, and Haiku 4.5
as "the most recent publicly available models" and doesn't mention Fable or
Mythos 5 anywhere. That's a real discrepancy I can't fully resolve myself —
it could simply mean my product info hasn't been updated to catch up with a
genuinely new release, or it could mean something about those search results
shouldn't be fully trusted. I don't have a way to be certain which.

Given that, here's how I scoped the work:

- **I did not build a large speculative feature set** around an unverified
  product, the way I'd build out a whole new tool category (like I did
  earlier for Cowork, Excel, PowerPoint).
- **I added what's directly actionable and low-risk either way**: Fable 5
  and Mythos 5 as selectable model IDs (the CLI already lets you pass any
  model string via `--model`, so this just makes them discoverable), plus
  client-side handling for the one genuinely new mechanic described —
  `stop_reason: "refusal"` responses with optional automatic fallback to
  another model. If the model doesn't exist or your account doesn't have
  access, calling it just returns a normal API error, the same as typing
  any other invalid model string.
- **Every place this shows up carries an explicit confidence caveat** —
  `zc_fable5.py`'s docstring, `--fable5-info`'s output, and the README
  section all say plainly: verify against platform.zc.com/docs and your
  own Console before relying on pricing/availability for anything that
  matters financially.

## New Commands

```bash
python main.py --fable5-info
python main.py --fable5 "your prompt"
python main.py --fable5 "your prompt" --fable5-no-fallback
python main.py --fable5 "your prompt" --fallback-model zc-sonnet-4-6
```

`--fable5-info` needs no API key or network call — it just prints the
static reference table. `--fable5` makes a real API call and will simply
fail clearly if `zc-fable-5` isn't a valid model for your account,
rather than pretending success.

## What I'd Suggest

Run `python main.py --fable5-info`, then check
[platform.zc.com/docs](https://platform.zc.com/docs) directly for
the current, authoritative status before you rely on any of this for
production use. If it turns out the model name or details are wrong, the
fix is a one-line edit to the `FABLE_MYTHOS_INFO` dict in `zc_fable5.py`
— I built it as a small, isolated, easily-correctable module specifically
because of that uncertainty.
