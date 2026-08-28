from wire.utils import sampling_kwargs

"""
zc_prompt_optimizer.py — Prompt Optimizer & A/B Tester
AI Model Coder CLI v1.9.1

Improves a prompt using meta-prompting, scores it, runs A/B tests
between two versions, and tracks a prompt library.

CLI flags:
  --optimize PROMPT         Rewrite a prompt to be clearer and more effective
  --score-prompt PROMPT     Score a prompt 0-100 for clarity, specificity, and completeness
  --ab-test                 With --prompt and --v2: A/B test two prompt variants
  --ab-task TASK            Task description to judge both variants against
  --prompt-lib-add          Save current --prompt to the library (use --tag for a label)
  --prompt-lib-list         List saved prompts
  --prompt-lib-get TAG      Retrieve a saved prompt by tag
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import anthropic

PROMPT_LIB_PATH = Path(os.path.expanduser("~/.ai-coder/prompt_library.json"))


def _call(client: anthropic.Anthropic, model: str, system: str,
          user: str, max_tokens: int = 2048) -> str:
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        **sampling_kwargs(model, temperature=0.3),
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def optimize(prompt: str, client: anthropic.Anthropic, model: str) -> str:
    system = (
        "You are an expert prompt engineer. Rewrite the user's prompt to be "
        "clearer, more specific, and more likely to get a great response from an AI. "
        "Return ONLY the improved prompt — no commentary, no explanation."
    )
    return _call(client, model, system, f"Prompt to improve:\n{prompt}")


def score(prompt: str, client: anthropic.Anthropic, model: str) -> dict:
    system = (
        "You are a prompt quality evaluator. Score this prompt on three dimensions "
        "(each 0-100): clarity, specificity, completeness. "
        "Return ONLY a JSON object: {\"clarity\": N, \"specificity\": N, \"completeness\": N, "
        "\"total\": N, \"feedback\": \"one sentence of the most impactful improvement\"}. "
        "Total = average of the three scores."
    )
    raw = _call(client, model, system, f"Prompt to score:\n{prompt}", max_tokens=512)
    try:
        cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "Could not parse score", "raw": raw}


def ab_test(prompt_a: str, prompt_b: str, task: str,
            client: anthropic.Anthropic, model: str) -> dict:
    def run(prompt: str) -> tuple[str, float]:
        t0 = time.time()
        resp = client.messages.create(
            model=model, max_tokens=2048,
            **sampling_kwargs(model, temperature=0.5),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip(), round(time.time() - t0, 2)

    resp_a, time_a = run(prompt_a)
    resp_b, time_b = run(prompt_b)

    judge_prompt = (
        f"Task: {task}\n\n"
        f"Response A:\n{resp_a}\n\n"
        f"Response B:\n{resp_b}\n\n"
        "Which response better completes the task? Reply ONLY with a JSON object: "
        "{\"winner\": \"A\" or \"B\" or \"tie\", \"reason\": \"one sentence\", "
        "\"score_a\": 0-100, \"score_b\": 0-100}"
    )
    judge_raw = _call(client, model,
                      "You are an objective evaluator of AI responses.", judge_prompt,
                      max_tokens=512)
    try:
        cleaned = judge_raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        judgment = json.loads(cleaned)
    except json.JSONDecodeError:
        judgment = {"winner": "unknown", "reason": judge_raw}

    return {
        "prompt_a": prompt_a, "response_a": resp_a, "time_a": time_a,
        "prompt_b": prompt_b, "response_b": resp_b, "time_b": time_b,
        "judgment": judgment,
    }


# ── Prompt Library ───────────────────────────────────────────────────────────

def _load_lib() -> dict:
    if PROMPT_LIB_PATH.exists():
        try:
            with open(PROMPT_LIB_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_lib(lib: dict):
    PROMPT_LIB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMPT_LIB_PATH, "w") as f:
        json.dump(lib, f, indent=2)


def lib_add(prompt: str, tag: str) -> str:
    lib = _load_lib()
    lib[tag] = {"prompt": prompt, "added": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save_lib(lib)
    return tag


def lib_list() -> list[dict]:
    lib = _load_lib()
    return [{"tag": k, "added": v.get("added", ""), "preview": v["prompt"][:80]}
            for k, v in lib.items()]


def lib_get(tag: str) -> Optional[str]:
    return _load_lib().get(tag, {}).get("prompt")


# ── CLI entry points ─────────────────────────────────────────────────────────

def cmd_optimize(prompt: str, api_key: str, model: str):
    client = anthropic.Anthropic(api_key=api_key)
    improved = optimize(prompt, client, model)
    print("\n\033[94mOriginal:\033[0m")
    print(prompt)
    print("\n\033[92mOptimized:\033[0m")
    print(improved)
    return improved


def cmd_score(prompt: str, api_key: str, model: str):
    client = anthropic.Anthropic(api_key=api_key)
    result = score(prompt, client, model)
    if "error" in result:
        print(f"\033[91mError: {result['error']}\033[0m")
        return
    print("\n\033[94mPrompt Score\033[0m")
    print(f"  Clarity:       {result.get('clarity', '?')}/100")
    print(f"  Specificity:   {result.get('specificity', '?')}/100")
    print(f"  Completeness:  {result.get('completeness', '?')}/100")
    print(f"  \033[1mTotal:         {result.get('total', '?')}/100\033[0m")
    print(f"  Feedback:      {result.get('feedback', '')}\n")


def cmd_ab_test(prompt_a: str, prompt_b: str, task: str, api_key: str, model: str):
    client = anthropic.Anthropic(api_key=api_key)
    result = ab_test(prompt_a, prompt_b, task, client, model)
    j = result["judgment"]
    print("\n\033[94mA/B Test Results\033[0m")
    print(f"  Winner:  \033[1m{j.get('winner', '?')}\033[0m  — {j.get('reason', '')}")
    print(f"  Score A: {j.get('score_a', '?')}/100  (response in {result['time_a']}s)")
    print(f"  Score B: {j.get('score_b', '?')}/100  (response in {result['time_b']}s)")
    print(f"\n\033[90m--- Response A ---\033[0m\n{result['response_a'][:400]}...")
    print(f"\n\033[90m--- Response B ---\033[0m\n{result['response_b'][:400]}...")


def cmd_prompt_lib_list():
    entries = lib_list()
    if not entries:
        print("Prompt library is empty. Use --prompt-lib-add with --tag to save prompts.")
        return
    print(f"\n\033[94mPrompt Library ({len(entries)} entries)\033[0m")
    for e in entries:
        print(f"  \033[1m{e['tag']:<20}\033[0m {e['preview']}")
    print()
