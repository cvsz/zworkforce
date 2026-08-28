"""
zc_cache.py — Prompt Caching
AI Model Coder CLI v1.18.0

Cache stable prompt prefixes (system prompts, documents, tool definitions)
to cut input token costs up to 90% and latency up to 85%.

Features:
  • Explicit cache breakpoints (cache_control markers)
  • 5-minute TTL (default) and 1-hour TTL caching
  • Cache pre-warming (max_tokens=0 dry-run)
  • Cache diagnostics (beta) — hit/miss reporting with cause (`cache_miss_reason`)
  • Mid-conversation system messages (Opus 4.8 only) — add/update system
    instructions partway through a conversation without invalidating the
    cached prefix that came before them (v1.18.0)
  • Multi-turn conversation caching
  • Tool-definition caching

CLI flags:
  --cache                  Enable prompt caching on this request
  --cache-ttl 5m|1h        Cache duration (default: 5m)
  --cache-warm             Pre-warm cache without generating output
  --cache-system TEXT      Cache a system prompt prefix
  --cache-stats            Show cache hit/miss stats from last response
  --cache-docs FILE [FILE ...]  Files to cache as document blocks
  --cache-diagnose          Opt into Cache diagnostics (beta) — report
                            cache_miss_reason against this instance's
                            previous call (see generate_cached(diagnose=));
                            the underlying support has existed in this
                            module since v1.10.x, this flag was the only
                            missing piece — nothing in main.py ever set
                            diagnose=True, so it was unreachable from the CLI
  --cache-mid-system TEXT  Append a mid-conversation system message (Opus
                            4.8 only) instead of touching the top-level
                            `system` field — see build_mid_system_message()

Mid-conversation system messages vs. the top-level `system` field:
  Use the top-level `system` field (--cache-system) for instructions that
  should apply from the very first turn. Use a mid-conversation system
  message (--cache-mid-system, role:"system" appended to `messages`) for
  instructions that only become relevant partway through a long,
  already-cached conversation — updating it doesn't touch the hashed
  system/tools prefix, so the existing cache entry still matches and only
  the new message is processed as fresh input. Both carry the same
  operator-level authority; per platform.zc.com/docs (checked
  2026-07-08), this is why untrusted content (raw tool output, retrieved
  documents, web content) must never be placed in either one — see
  validate_system_message_placement() for the placement rules the API
  enforces (400 error if violated) and MID_SYSTEM_SUPPORTED_MODELS for
  which models accept role:"system" in `messages` at all.
"""

import json
import urllib.error
import urllib.request
from typing import Optional, Any, Union

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# ── Mid-conversation system messages (v1.18.0) ──────────────────────────────
# Per platform.zc.com/docs/en/build-with-zc/mid-conversation-system-messages
# (checked 2026-07-08): available on the zAICoder API, zAICoder Platform on AWS,
# and Microsoft Foundry; NOT on Amazon Bedrock or Google Cloud. Opus 4.8
# only, no beta header required. wire only talks to the direct zAICoder API,
# so the AWS/Foundry-vs-Bedrock/Google-Cloud split isn't relevant here, but
# the model gate is.
MID_SYSTEM_SUPPORTED_MODELS = {"zc-opus-4-8"}


class SystemMessagePlacementError(ValueError):
    """Raised when a mid-conversation system message would violate the
    API's documented placement rules (these return a 400 error server-side;
    validating client-side catches it before spending a round trip)."""


def build_mid_system_message(text: str) -> dict:
    """Build a {"role": "system", ...} message for the `messages` array.

    Content supports text blocks only — no images, documents, tool blocks,
    or citations (per docs). This is a *message*, not the top-level
    `system` field: it carries the same operator-level authority, so never
    build one from untrusted content (tool output, retrieved documents,
    web content) — that would grant that text operator authority.
    """
    return {"role": "system", "content": [{"type": "text", "text": text}]}


def validate_system_message_placement(messages: list[dict]) -> None:
    """Validate every role:"system" entry in `messages` against the
    documented placement rules. Raises SystemMessagePlacementError on the
    first violation found; does nothing if there are no system messages or
    all of them are correctly placed.

    Rules (platform.zc.com/docs, checked 2026-07-08):
      - Cannot be the first entry in `messages`.
      - Must immediately follow a user turn (including one carrying
        tool_result blocks) or an assistant turn that ends in a server
        tool use.
      - Must either be the last entry in `messages` or be followed by an
        assistant turn.
      - Cannot sit between a tool_use block and its tool_result.
      - Cannot be adjacent to another system message (no consecutive
        system messages).
    """
    def _is_system(m: dict) -> bool:
        return m.get("role") == "system"

    def _block_types(content) -> set:
        if isinstance(content, str):
            return set()
        return {b.get("type") for b in (content or []) if isinstance(b, dict)}

    for i, msg in enumerate(messages):
        if not _is_system(msg):
            continue

        if i == 0:
            raise SystemMessagePlacementError(
                "A system message cannot be the first entry in messages; "
                "use the top-level `system` field for turn-one instructions.")

        prev = messages[i - 1]
        if _is_system(prev):
            raise SystemMessagePlacementError(
                f"System message at index {i} is adjacent to another system "
                f"message at index {i-1}; consecutive system messages are "
                "not allowed.")

        prev_types = _block_types(prev.get("content"))

        # An assistant turn ending in a client-side tool_use (not
        # server_tool_use) is always followed by that tool's tool_result —
        # inserting a system message right after it would sit between the
        # tool_use and its tool_result, which is invalid regardless of the
        # more general "must follow user/server-tool-use" rule below.
        if prev.get("role") == "assistant" and "tool_use" in prev_types \
                and "server_tool_use" not in prev_types:
            raise SystemMessagePlacementError(
                f"System message at index {i} cannot sit between a tool_use "
                "block and its tool_result.")

        prev_ok = (
            prev.get("role") == "user"
            or (prev.get("role") == "assistant" and "server_tool_use" in prev_types)
        )
        if not prev_ok:
            raise SystemMessagePlacementError(
                f"System message at index {i} must immediately follow a user "
                "turn or an assistant turn ending in server tool use "
                f"(preceding message has role={prev.get('role')!r}).")

        if i < len(messages) - 1:
            nxt = messages[i + 1]
            if _is_system(nxt):
                raise SystemMessagePlacementError(
                    f"System message at index {i} is adjacent to another "
                    f"system message at index {i+1}; consecutive system "
                    "messages are not allowed.")
            if nxt.get("role") != "assistant":
                raise SystemMessagePlacementError(
                    f"System message at index {i} must be the last entry in "
                    f"messages or be followed by an assistant turn "
                    f"(next message has role={nxt.get('role')!r}).")


# ── Low-level helpers ──────────────────────────────────────────────────────

def _make_cache_control(ttl: str = "5m") -> dict:
    """Build a cache_control block."""
    if ttl == "1h":
        return {"type": "ephemeral", "ttl": 3600}
    return {"type": "ephemeral"}          # 5-minute default


def _add_cache_breakpoint(block: dict, ttl: str = "5m") -> dict:
    """Return a copy of block with cache_control injected."""
    b = dict(block)
    b["cache_control"] = _make_cache_control(ttl)
    return b


# ── CachingCoder ──────────────────────────────────────────────────────────

class CachingCoder:
    """zAICoder client with explicit prompt-caching support."""

    ENDPOINT = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 max_tokens: int = 4096, ttl: str = "5m"):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens
        self.ttl        = ttl          # "5m" or "1h"
        self._last_usage: dict = {}
        self._last_message_id: Optional[str] = None
        self._last_cache_miss_reason: Optional[str] = None

    def _post(self, payload: dict, diagnose: bool = False) -> dict:
        body    = json.dumps(payload).encode()
        betas   = ["prompt-caching-2024-07-31"]
        if diagnose:
            # Cache diagnostics (public beta). Per platform.zc.com/docs
            # (checked 2026-07-02): pass diagnostics.previous_message_id on
            # the request and the API reports cache_miss_reason explaining
            # where the prompt cache prefix diverged from that previous
            # turn. Was entirely missing — no way to see *why* a cache miss
            # happened, only that usage showed 0 cache_read_input_tokens.
            betas.append("cache-diagnosis-2026-04-07")
        headers = {
            "Content-Type":    "application/json",
            "x-api-key":       self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":  ",".join(betas),
        }
        req = urllib.request.Request(self.ENDPOINT, data=body,
                                     headers=headers, method="POST")
        try:
            return self._call(req)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, req: "urllib.request.Request") -> dict:
        return urlopen_json(req, timeout=120)

    # ── Single cached call ─────────────────────────────────────────────────

    def generate_cached(
        self,
        prompt: str,
        system: Optional[str] = None,
        cached_docs: Optional[list[str]] = None,
        history: Optional[list[dict]] = None,
        diagnose: bool = False,
        mid_system: Optional[str] = None,
    ) -> str:
        """
        Call zAICoder with cache breakpoints on system + docs.
        cached_docs: list of large document strings to cache.
        diagnose=True asks the API to explain a cache miss against the
        previous call this instance made (self._last_message_id) — see
        cache_miss_reason on cache_stats()/print_cache_stats() afterward.
        Only meaningful from the second call in a sequence onward; the
        first call has no previous_message_id to compare against.
        mid_system: if given, appends a mid-conversation system message
        (build_mid_system_message()) to `history` before the new user
        turn — updates zAICoder's instructions without touching the
        top-level `system` field, so it doesn't invalidate the cached
        prefix. Opus 4.8 only (MID_SYSTEM_SUPPORTED_MODELS); raises
        ValueError on an unsupported model, and
        SystemMessagePlacementError if the resulting `messages` array
        would violate the documented placement rules (e.g. mid_system
        given with no prior history to follow).
        """
        messages = list(history or [])

        if mid_system:
            if self.model not in MID_SYSTEM_SUPPORTED_MODELS:
                raise ValueError(
                    f"Mid-conversation system messages require one of "
                    f"{sorted(MID_SYSTEM_SUPPORTED_MODELS)}; got {self.model!r}. "
                    "Use the top-level `system` field (--cache-system) instead.")
            messages.append(build_mid_system_message(mid_system))
            validate_system_message_placement(messages)

        # Build user content
        user_blocks = []
        for doc in (cached_docs or []):
            user_blocks.append(_add_cache_breakpoint(
                {"type": "text", "text": doc}, self.ttl
            ))
        user_blocks.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": user_blocks})

        payload: dict = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "messages":   messages,
        }

        # Cache the system prompt
        if system:
            payload["system"] = [
                _add_cache_breakpoint({"type": "text", "text": system}, self.ttl)
            ]

        if diagnose:
            # Docs opt in on every call, using previous_message_id: None on
            # the very first one (nothing to compare against yet).
            payload["diagnostics"] = {"previous_message_id": self._last_message_id}

        data = self._post(payload, diagnose=diagnose)
        if "error" in data:
            return f"[API ERROR] {data['error']}"

        self._last_usage = data.get("usage", {})
        self._last_message_id = data.get("id") or self._last_message_id
        # diagnostics is a top-level field on the response, not part of
        # usage — {"cache_miss_reason": {"type": "system_changed", ...}} or
        # null if no divergence was detected (or the comparison is still
        # pending on a very first call).
        diag = data.get("diagnostics") or {}
        miss = diag.get("cache_miss_reason") or {}
        self._last_cache_miss_reason = miss.get("type")
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    # ── Cache pre-warming ──────────────────────────────────────────────────

    def warm_cache(self, system: Optional[str] = None, docs: Optional[list[str]] = None) -> dict:
        """
        Pre-warm cache by sending a max_tokens=0 request.
        No output is produced and no output tokens are billed.
        Returns usage showing cache_creation_input_tokens.
        """
        user_blocks = [
            _add_cache_breakpoint({"type": "text", "text": d}, self.ttl)
            for d in (docs or [])
        ]
        user_blocks.append({"type": "text", "text": "."})  # minimal user msg

        payload: dict = {
            "model":      self.model,
            "max_tokens": 1,          # minimal to satisfy API
            "messages":   [{"role": "user", "content": user_blocks}],
        }
        if system:
            payload["system"] = [
                _add_cache_breakpoint({"type": "text", "text": system}, self.ttl)
            ]

        data = self._post(payload)
        self._last_usage = data.get("usage", {})
        return self._last_usage

    # ── Tool-definition caching ────────────────────────────────────────────

    def generate_with_cached_tools(
        self,
        prompt: str,
        tools: list[dict],
        system: Optional[str] = None,
    ) -> str:
        """Cache tool definitions at the tools level (invalidated only if tools change)."""
        if tools:
            # Mark the last tool with cache_control
            tools = list(tools)
            tools[-1] = dict(tools[-1])
            tools[-1]["cache_control"] = _make_cache_control(self.ttl)

        messages = [{"role": "user", "content": prompt}]
        payload: dict = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "messages":   messages,
            "tools":      tools,
        }
        if system:
            payload["system"] = [
                _add_cache_breakpoint({"type": "text", "text": system}, self.ttl)
            ]

        data = self._post(payload)
        if "error" in data:
            return f"[API ERROR] {data['error']}"

        self._last_usage = data.get("usage", {})
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    # ── Multi-turn with caching ────────────────────────────────────────────

    def multi_turn_cached(
        self,
        turns: list[str],
        system: Optional[str] = None,
        mid_system_updates: Optional[dict] = None,
    ) -> list[str]:
        """
        Run a multi-turn conversation, caching the growing history each turn.
        Each assistant response is appended before the next user turn.

        mid_system_updates: optional {turn_index: text} map (0-based,
        turn_index i means "after sending turns[i]'s user message"). Each
        entry inserts a mid-conversation system message
        (build_mid_system_message()) right after that turn's user message
        and before the assistant reply — satisfying the documented
        placement rule (system message immediately follows a user turn,
        and is the last entry in `messages` when the request goes out,
        which satisfies "last entry or followed by an assistant turn").
        Requires self.model in MID_SYSTEM_SUPPORTED_MODELS (Opus 4.8);
        raises ValueError otherwise.
        """
        if mid_system_updates and self.model not in MID_SYSTEM_SUPPORTED_MODELS:
            raise ValueError(
                f"Mid-conversation system messages require one of "
                f"{sorted(MID_SYSTEM_SUPPORTED_MODELS)}; got {self.model!r}.")

        messages: list[dict[str, Any]] = []
        responses = []
        mid_system_updates = mid_system_updates or {}

        for idx, turn in enumerate(turns):
            # Cache the entire message history so far
            if messages:
                # Add cache_control to last message
                last = dict(messages[-1])
                content_val = last.get("content", "")
                
                content_list: list[dict[str, Any]] = []
                if isinstance(content_val, str):
                    content_list = [{"type": "text", "text": content_val}]
                elif isinstance(content_val, list):
                    content_list = list(content_val)
                    
                if content_list:
                    content_list[-1] = _add_cache_breakpoint(content_list[-1], self.ttl)
                last["content"] = content_list
                messages[-1] = last

            messages.append({"role": "user", "content": turn})

            if idx in mid_system_updates:
                messages.append(build_mid_system_message(mid_system_updates[idx]))
                validate_system_message_placement(messages)

            payload: dict = {
                "model":      self.model,
                "max_tokens": self.max_tokens,
                "messages":   messages,
            }
            if system:
                payload["system"] = [
                    _add_cache_breakpoint({"type": "text", "text": system}, self.ttl)
                ]

            data = self._post(payload)
            self._last_usage = data.get("usage", {})

            if "error" in data:
                responses.append(f"[ERROR] {data['error']}")
                break

            resp_text = "".join(
                b.get("text", "") for b in data.get("content", [])
                if b.get("type") == "text"
            )
            responses.append(resp_text)
            messages.append({"role": "assistant", "content": resp_text})

        return responses

    # ── Cache stats ────────────────────────────────────────────────────────

    def cache_stats(self) -> dict:
        u = self._last_usage
        return {
            "input_tokens":                u.get("input_tokens", 0),
            "output_tokens":               u.get("output_tokens", 0),
            "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens":     u.get("cache_read_input_tokens", 0),
            # Only populated when the last generate_cached() call passed
            # diagnose=True and the API had a previous request to compare
            # against — see Cache diagnostics (beta) in generate_cached().
            "cache_miss_reason":           self._last_cache_miss_reason,
        }

    def print_cache_stats(self):
        s = self.cache_stats()
        hit  = s["cache_read_input_tokens"]
        miss = s["cache_creation_input_tokens"]
        inp  = s["input_tokens"]
        out  = s["output_tokens"]
        ratio = f"{hit/(hit+miss+inp)*100:.1f}%" if (hit+miss+inp) > 0 else "—"
        print("\n\033[90m── Cache Stats ─────────────────────────")
        print(f"  input tokens:        {inp}")
        print(f"  cache write tokens:  {miss}  (billed at 1.25x)")
        print(f"  cache read tokens:   {hit}  (billed at 0.1x)")
        print(f"  output tokens:       {out}")
        print(f"  cache hit rate:      {ratio}")
        if s["cache_miss_reason"]:
            print(f"  cache miss reason:   {s['cache_miss_reason']}  (diagnostics beta)")
        print("──────────────────────────────────────\033[0m")


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_cache_generate(prompt: str, api_key: str, model: str, system: Optional[str] = None,
                       docs: Optional[list[str]] = None, ttl: str = "5m",
                       show_stats: bool = True, diagnose: bool = False) -> str:
    print(f"\033[94mℹ Prompt caching enabled (TTL={ttl})\033[0m\n")
    cc = CachingCoder(api_key=api_key, model=model, ttl=ttl)
    result = cc.generate_cached(prompt, system=system, cached_docs=docs, diagnose=diagnose)
    print(result)
    if show_stats:
        cc.print_cache_stats()
    return result


def cmd_cache_multi_turn(turns: list[str], api_key: str, model: str,
                         system: Optional[str] = None, ttl: str = "5m",
                         mid_system: Optional[str] = None, mid_system_after: int = 0,
                         show_stats: bool = True) -> list[str]:
    """
    Run a multi-turn cached conversation. If mid_system is given, it's
    inserted as a mid-conversation system message immediately after
    turns[mid_system_after] (0-based) — see multi_turn_cached() and
    Mid-conversation system messages (Opus 4.8 only) in the module
    docstring. Requires at least 2 turns so there's an assistant reply
    downstream of the injected instruction to demonstrate the effect.
    """
    print(f"\033[94mℹ Prompt caching enabled (TTL={ttl}, {len(turns)} turns)\033[0m")
    if mid_system:
        print(f"\033[94mℹ Mid-conversation system message queued after turn "
              f"{mid_system_after}: {mid_system!r}\033[0m")
    cc = CachingCoder(api_key=api_key, model=model, ttl=ttl)
    updates = {mid_system_after: mid_system} if mid_system else None
    try:
        responses = cc.multi_turn_cached(turns, system=system,
                                         mid_system_updates=updates)
    except (ValueError, SystemMessagePlacementError) as e:
        print(f"\033[91m✗ {e}\033[0m")
        return []
    for i, r in enumerate(responses):
        print(f"\n\033[90m── Turn {i+1} ──\033[0m\n{r}")
    if show_stats:
        cc.print_cache_stats()
    return responses


def cmd_cache_warm(api_key: str, model: str, system: Optional[str] = None,
                   doc_files: Optional[list[str]] = None, ttl: str = "5m"):
    print(f"\033[94mℹ Pre-warming cache (TTL={ttl})…\033[0m")
    docs = []
    for f in (doc_files or []):
        try:
            with open(f) as fh:
                docs.append(fh.read())
        except Exception as e:
            print(f"  [WARN] Cannot read {f}: {e}")

    cc    = CachingCoder(api_key=api_key, model=model, ttl=ttl)
    usage = cc.warm_cache(system=system, docs=docs)
    created = usage.get("cache_creation_input_tokens", 0)
    print(f"\033[92m✓ Cache warmed — {created} tokens written to cache\033[0m")
    cc.print_cache_stats()
