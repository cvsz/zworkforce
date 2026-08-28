"""
zc_router.py — Multi-Agent Conversation Router
AI Model Coder CLI v1.9.1

Routes every incoming prompt to the most appropriate specialist agent
by asking a lightweight classifier call first, then forwarding to the
winner. Supports fallback chains and parallel fan-out.

CLI flags:
  --route PROMPT                     Auto-route PROMPT to the best specialist agent
  --route-explain                    With --route: print which agent was chosen and why
  --route-parallel                   Fan-out to ALL agents and return the best answer
  --route-add-agent NAME DESCRIPTION Register a custom agent for this invocation only
                                      (repeatable). Combine with --route or --route-list;
                                      has no effect used alone.
  --route-list                       List all agents in the routing table

v1.32.0: --route-add-agent was documented above since v1.9.1 but had no
cmd_* function backing it, so the v1.31.0 CLI-wiring sweep (which wires
cmd_* functions, not docstring promises) correctly left it out and filed
it as a follow-up -- see docs/44_upgrade_v1.32.0_route_add_agent.md. The
open question was never "does the plumbing exist" (route_and_call(),
cmd_route(), and cmd_route_list() have taken an extra_table: Optional[dict]
since day one) but "how does a two-part NAME+DESCRIPTION value get
expressed as a flag". Resolved as a repeatable nargs=2 flag, same shape
as --git-pr BASE HEAD and --eval-compare MODEL_A MODEL_B elsewhere in
main.py; see extra_table_from_pairs() below for the NAME,DESCRIPTION
list -> dict step. Deliberately per-invocation, not persisted to disk --
unlike --hooks-add or the prompt library, a custom agent here only lives
as long as the process does.
"""

import json
import urllib.error
import urllib.request
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json
from wire.utils import sampling_kwargs

ENDPOINT = "https://api.anthropic.com/v1/messages"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# ── Built-in routing table ──────────────────────────────────────────────────
DEFAULT_ROUTING_TABLE = {
    "code":          "Write, review, refactor, debug, or explain code in any language",
    "research":      "Deep factual research, literature review, or evidence synthesis",
    "write":         "Long-form writing, editing, summarisation, translation, or copywriting",
    "analyse":       "Data analysis, statistical interpretation, or business insight extraction",
    "plan":          "Project planning, task breakdown, roadmaps, or strategy",
    "brainstorm":    "Idea generation, creative thinking, or blue-sky exploration",
    "security":      "Security review, threat modelling, CVE analysis, or hardening advice",
    "architect":     "System design, architecture decisions, or technology selection",
    "debug":         "Root-cause analysis and bug fixing for code or systems",
    "automate":      "Workflow automation, scripting, CI/CD, or DevOps pipeline design",
}


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _call(api_key: str, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(),
        headers=headers, method="POST",
    )
    return urlopen_json(req, timeout=60)


def _post(api_key: str, payload: dict) -> dict:
    # Preserves the pre-existing {"error": ...} contract callers below
    # already check for, while retrying transient failures in _call().
    try:
        return _call(api_key, payload)
    except AICoderError as e:
        return {"error": e.message}
    except Exception as e:
        return {"error": str(e)}


def _text(data: dict) -> str:
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def classify(prompt: str, table: dict, api_key: str, model: str) -> tuple[str, str]:
    """Return (agent_name, reason) for the best-fit agent."""
    options = "\n".join(f"  {k}: {v}" for k, v in table.items())
    classifier_prompt = (
        f"You are a routing classifier. Given a user request, choose the single best "
        f"specialist agent from the list below. Reply with ONLY a JSON object: "
        f'{{\"agent\": \"<agent_name>\", \"reason\": \"<one sentence>\"}}\n\n'
        f"Agents:\n{options}\n\nUser request: {prompt}"
    )
    data = _post(api_key, {
        "model": model, "max_tokens": 200,
        **sampling_kwargs(model, temperature=0.0),
        "messages": [{"role": "user", "content": classifier_prompt}],
    })
    raw = _text(data).strip()
    try:
        parsed = json.loads(raw)
        agent = parsed.get("agent", "code")
        reason = parsed.get("reason", "")
        if agent not in table:
            agent = "code"
        return agent, reason
    except (json.JSONDecodeError, KeyError):
        return "code", "classifier output not parseable; defaulting to code agent"


def route_and_call(
    prompt: str,
    api_key: str,
    model: str,
    table: Optional[dict] = None,
    explain: bool = False,
    parallel: bool = False,
) -> str:
    table = table or DEFAULT_ROUTING_TABLE

    if parallel:
        results = {}
        for agent_name, description in table.items():
            system = f"You are a specialist in: {description}. Answer as that expert."
            data = _post(api_key, {
                "model": model, "max_tokens": 2048,
                **sampling_kwargs(model, temperature=0.5),
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            })
            results[agent_name] = _text(data)
        # Synthesise the best answer
        synthesis_prompt = (
            "Multiple specialist agents answered this question. "
            "Synthesise the best, most complete answer, crediting unique insights "
            "from each agent where relevant.\n\n"
            + "\n\n".join(f"[{k.upper()}]\n{v}" for k, v in results.items())
            + f"\n\nOriginal question: {prompt}"
        )
        data = _post(api_key, {
            "model": model, "max_tokens": 4096,
            **sampling_kwargs(model, temperature=0.3),
            "messages": [{"role": "user", "content": synthesis_prompt}],
        })
        return _text(data)

    agent_name, reason = classify(prompt, table, api_key, model)
    if explain:
        print(f"\033[90m→ Routing to [{agent_name}]: {reason}\033[0m\n")

    system = f"You are a specialist in: {table[agent_name]}. Answer as that expert."
    data = _post(api_key, {
        "model": model, "max_tokens": 4096,
        **sampling_kwargs(model, temperature=0.6),
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    })
    return _text(data)


def extra_table_from_pairs(pairs: Optional[list]) -> Optional[dict]:
    """Turn repeated --route-add-agent NAME DESCRIPTION flags into the
    extra_table dict cmd_route() / cmd_route_list() already accept.

    argparse's nargs=2 + action="append" collects each occurrence as a
    [NAME, DESCRIPTION] pair into a list, e.g.
    [["frontend", "React and CSS"], ["infra", "Terraform and k8s"]].
    This just folds that into {"frontend": "React and CSS", ...}.

    Returns None (not {}) when pairs is falsy, so every call site can do
    extra_table=extra_table_from_pairs(args.route_add_agent) and get the
    same "no custom agents" behavior as today's default of None, instead
    of needing an `if args.route_add_agent else None` at each one.

    Duplicate NAMEs: last one wins, same last-write-wins semantics as
    table.update(extra_table) below -- no special-casing needed.
    """
    if not pairs:
        return None
    return {name: description for name, description in pairs}


def cmd_route(prompt: str, api_key: str, model: str,
              explain: bool = False, parallel: bool = False,
              extra_table: Optional[dict] = None):
    table = dict(DEFAULT_ROUTING_TABLE)
    if extra_table:
        table.update(extra_table)
    answer = route_and_call(prompt, api_key, model, table, explain, parallel)
    print(answer)


def cmd_route_list(extra_table: Optional[dict] = None):
    table = dict(DEFAULT_ROUTING_TABLE)
    if extra_table:
        table.update(extra_table)
    print("\n\033[94mRouting Table\033[0m")
    for name, desc in sorted(table.items()):
        print(f"  \033[1m{name:<14}\033[0m {desc}")
    print()