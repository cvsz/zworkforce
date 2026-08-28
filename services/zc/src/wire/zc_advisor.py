"""
zc_advisor.py — Advisor tool (advisor_20260301, beta)
AI Model Coder CLI v1.11.0

This was a complete gap before this pass: the advisor tool did not exist
anywhere in the project. It's a server tool that pairs a faster "executor"
model with a stronger "advisor" model the executor can consult mid-generation
at decision points (before committing to an approach, when stuck on a
recurring error, before declaring a task complete). The advisor sees the
full transcript and returns guidance the executor applies before continuing;
it never calls tools and never produces the user-facing final answer itself.

IMPORTANT — confidence note (same posture as zc_fable5.py's for its own
model family): the request/response shape below is taken from
platform.zc.com/docs/en/agents-and-tools/tool-use/advisor-tool and a
third-party worked example, checked 2026-07-02. This is a beta feature this
project has no independent way to verify beyond what the live API reports
at call time. Re-verify field names against your own account before relying
on this for anything billing- or production-sensitive.

Mechanics, as documented:
  • Add a tool of type "advisor_20260301" to your tools array, with its own
    "model" (the advisor model), optional "max_uses", optional "caching".
  • The executor emits a server_tool_use block named "advisor" when it wants
    guidance; the API runs the advisor pass server-side and returns the
    result as an advisor_tool_result block in the SAME response — no extra
    round trip needed on your part, UNLESS the response ends with
    stop_reason:"pause_turn" while an advisor call is still pending. In that
    case, resume by resending the assistant message unchanged (including the
    pending server_tool_use block) with the advisor tool still present.
  • If you omit the advisor tool from a follow-up request while the message
    history still contains advisor_tool_result blocks, the API 400s. Once
    you're done with the advisor for a conversation, strip those blocks too.
  • Supported executor models (beta): Opus 4.6+, Sonnet 4.6+, Haiku 4.5,
    Fable 5. Not available on Bedrock, Vertex AI, or Microsoft Foundry.
  • Advisor output tokens are billed at the advisor model's own rate — this
    is usually the dominant cost line, not the executor's tokens.

CLI flags:
  --advisor PROMPT           Run PROMPT with an advisor attached
  --advisor-model MODEL      Advisor model (default: zc-opus-4-8)
  --advisor-max-uses N       Cap advisor calls this conversation (client-side
                              tracking — the tool itself has no built-in cap)
  --advisor-max-tokens N     Cap the advisor's output per call (max_tokens on
                              the advisor tool definition)
"""

import json
import urllib.error
import urllib.request
from typing import Any, Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

ADVISOR_TOOL_TYPE = "advisor_20260301"
ADVISOR_TOOL_BETA = "advisor-tool-2026-03-01"
ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# Executor models the advisor tool is documented to support as of this
# check. Haiku working as an executor is real but weaker — Anthropic's own
# eval note says a short reminder message on turn 2 raises Haiku pass rates
# ~7pp if it hasn't called the advisor in its first assistant turn.
ADVISOR_EXECUTOR_MODELS = {
    "zc-opus-4-8", "zc-opus-4-7", "zc-opus-4-6",
    "zc-xxx", "zc-sonnet-4-6",
    "zc-haiku-4-5", "zc-haiku-4-5-20251001",
    "zc-fable-5",
}


def build_advisor_tool(advisor_model: str = "zc-opus-4-8",
                        max_uses: Optional[int] = None,
                        max_tokens: Optional[int] = None,
                        cache_ttl: Optional[str] = "5m") -> dict:
    """Build the advisor tool definition. cache_ttl caches the advisor's own
    read of the conversation (ephemeral, 5m default) so repeated advisor
    calls in one session don't re-process the full transcript from scratch
    every time — set to None to disable."""
    tool: dict[str, Any] = {
        "type":  ADVISOR_TOOL_TYPE,
        "name":  "advisor",
        "model": advisor_model,
    }
    if max_uses is not None:
        tool["max_uses"] = max_uses
    if max_tokens is not None:
        tool["max_tokens"] = max_tokens
    if cache_ttl:
        tool["caching"] = {"type": "ephemeral", "ttl": cache_ttl}
    return tool


class AdvisorCoder:
    """zAICoder client wired to run an executor model with an advisor tool
    attached, including the pause_turn resume loop the advisor tool uses
    when it needs to hand a pending call back to you before continuing."""

    def __init__(self, api_key: str, executor_model: str = "zc-xxx",
                 max_tokens: int = 4096):
        self.api_key        = api_key
        self.executor_model = executor_model
        self.max_tokens     = max_tokens
        if executor_model not in ADVISOR_EXECUTOR_MODELS:
            print(f"\033[93m⚠ {executor_model} isn't in the documented advisor-tool "
                  f"executor list ({sorted(ADVISOR_EXECUTOR_MODELS)}) — sending anyway, "
                  f"the API will reject it if unsupported.\033[0m")

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    ADVISOR_TOOL_BETA,
        }
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload).encode(),
            headers=headers, method="POST",
        )
        return urlopen_json(req, timeout=180)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def run(self, prompt: str, advisor_tool: dict,
            extra_tools: Optional[list[dict]] = None,
            system: Optional[str] = None,
            max_advisor_calls: int = 10,
            verbose: bool = True) -> str:
        """Single user turn, resolving any pause_turn advisor round trips
        along the way. max_advisor_calls is client-side bookkeeping (the
        advisor tool has no built-in conversation-level cap per the docs);
        once hit, the advisor tool is dropped from tools and any
        advisor_tool_result blocks are stripped from history, matching the
        documented approach for retiring the advisor mid-conversation."""
        tools    = [advisor_tool] + (extra_tools or [])
        messages = [{"role": "user", "content": prompt}]
        advisor_calls = 0

        while True:
            payload: dict = {
                "model":      self.executor_model,
                "max_tokens": self.max_tokens,
                "messages":   messages,
                "tools":      tools,
            }
            if system:
                payload["system"] = system

            data = self._post(payload)
            if "error" in data:
                return f"[ERROR] {data['error']}"

            stop_reason = data.get("stop_reason", "")
            content     = data.get("content", [])

            for block in content:
                if block.get("type") == "server_tool_use" and block.get("name") == "advisor":
                    advisor_calls += 1
                    if verbose:
                        print(f"\033[90m  [advisor call #{advisor_calls}]\033[0m")
                if block.get("type") == "advisor_tool_result" and verbose:
                    txt = "".join(
                        c.get("text", "") for c in block.get("content", [])
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                    if txt:
                        print(f"\033[90m  [advisor guidance] {txt[:200]}"
                              f"{'...' if len(txt) > 200 else ''}\033[0m")

            messages.append({"role": "assistant", "content": content})

            if stop_reason == "pause_turn":
                if advisor_calls >= max_advisor_calls:
                    if verbose:
                        print(f"\033[93m⚠ max_advisor_calls ({max_advisor_calls}) reached — "
                              f"dropping the advisor tool and continuing without it.\033[0m")
                    tools = [t for t in tools if t.get("type") != ADVISOR_TOOL_TYPE]
                    messages = _strip_advisor_blocks(messages)
                # No new user message or tool_result needed — just resend;
                # the API runs the pending advisor call and continues.
                continue

            if stop_reason == "tool_use":
                # A client tool was called in the same turn as a pending
                # advisor call. Caller must execute those and send results;
                # this simple loop only handles the advisor-only case.
                pending = [b for b in content if b.get("type") == "tool_use"]
                if pending:
                    return ("[TOOL_USE] Executor called client tool(s) "
                            f"{[b['name'] for b in pending]} — send tool_result "
                            f"blocks and resend to continue (see 'Mixing server "
                            f"tools and client tools in one turn').")
                continue

            if stop_reason == "end_turn":
                return "".join(b.get("text", "") for b in content if b.get("type") == "text")

            return f"[UNEXPECTED stop_reason={stop_reason}]"


def _strip_advisor_blocks(messages: list) -> list:
    """Remove server_tool_use(advisor) / advisor_tool_result blocks from
    history before dropping the advisor tool — the API 400s if it sees
    advisor_tool_result blocks without the advisor tool present."""
    cleaned = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            content = [
                b for b in content
                if not (isinstance(b, dict) and (
                    (b.get("type") == "server_tool_use" and b.get("name") == "advisor")
                    or b.get("type") == "advisor_tool_result"
                ))
            ]
        cleaned.append({**m, "content": content})
    return cleaned


# ── CLI entry point ─────────────────────────────────────────────────────────

def cmd_advisor(prompt: str, api_key: str, executor_model: str,
                advisor_model: str = "zc-opus-4-8",
                max_uses: Optional[int] = None,
                advisor_max_tokens: Optional[int] = None):
    print(f"\033[94mℹ Advisor tool | executor={executor_model} advisor={advisor_model}\033[0m\n")
    advisor_tool = build_advisor_tool(
        advisor_model=advisor_model, max_uses=max_uses, max_tokens=advisor_max_tokens,
    )
    ac = AdvisorCoder(api_key=api_key, executor_model=executor_model)
    result = ac.run(prompt, advisor_tool)
    print(result)
    return result