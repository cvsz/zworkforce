"""
zc_eval.py — Evaluation harness for prompts, agents, and skills.
Run a test suite of (input, expected) pairs, score responses, and
compare two model/prompt configurations head-to-head.
AI Model Coder CLI v1.10.0
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from wire.utils import sampling_kwargs

EVALS_DIR = Path.home() / ".ai-coder" / "evals"


@dataclass
class EvalCase:
    case_id:  str
    prompt:   str
    expected: str
    tags:     list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    case_id:    str
    prompt:     str
    expected:   str
    actual:     str
    score:      float       # 0.0–1.0
    passed:     bool
    latency_ms: int
    model:      str
    reason:     str = ""


@dataclass
class EvalRun:
    run_id:  str
    model:   str
    cases:   int
    passed:  int
    avg_score: float
    avg_latency_ms: float
    results: list[EvalResult]
    ts:      str = field(default_factory=lambda: datetime.now().isoformat())

    def summary(self) -> str:
        return (f"Run {self.run_id}  model={self.model}  "
                f"{self.passed}/{self.cases} passed  "
                f"avg_score={self.avg_score:.2f}  "
                f"avg_latency={self.avg_latency_ms:.0f}ms")


class LLMJudge:
    """Uses zAICoder to judge whether a response satisfies the expected criterion."""

    def __init__(self, api_key: str, judge_model: str = "zc-xxx"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = judge_model

    def score(self, prompt: str, expected: str, actual: str) -> tuple[float, str]:
        """Return (score 0–1, reason)."""
        system = (
            "You are an evaluation judge. Score the response 0.0–1.0 where:\n"
            "1.0 = fully satisfies the expected criterion\n"
            "0.5 = partially satisfies\n"
            "0.0 = does not satisfy at all\n"
            "Return ONLY a JSON object: {\"score\": float, \"reason\": str}"
        )
        user = (
            f"Task prompt: {prompt}\n\n"
            f"Expected criterion: {expected}\n\n"
            f"Actual response:\n{actual}\n\n"
            "Score the actual response against the expected criterion."
        )
        try:
            resp = self.client.messages.create(
                model=self.model, max_tokens=256,
                **sampling_kwargs(self.model, temperature=0),
                system=system, messages=[{"role": "user", "content": user}])
            raw = resp.content[0].text.strip()
            if raw.startswith("```"): raw = "\n".join(raw.split("\n")[1:-1])
            d = json.loads(raw)
            return float(d.get("score", 0.0)), str(d.get("reason", ""))
        except Exception as e:
            return 0.0, f"judge error: {e}"


class EvalRunner:
    def __init__(self, api_key: str, model: str = "zc-xxx",
                 judge_model: str = "zc-xxx", pass_threshold: float = 0.7):
        self.client    = anthropic.Anthropic(api_key=api_key)
        self.model     = model
        self.judge     = LLMJudge(api_key, judge_model)
        self.threshold = pass_threshold

    def _generate(self, prompt: str) -> tuple[str, int]:
        t0 = time.time()
        resp = self.client.messages.create(
            model=self.model, max_tokens=2048,
            **sampling_kwargs(self.model, temperature=0),
            messages=[{"role": "user", "content": prompt}])
        ms = int((time.time() - t0) * 1000)
        return resp.content[0].text, ms

    def run(self, cases: list[EvalCase]) -> EvalRun:
        import uuid
        run_id  = str(uuid.uuid4())[:8]
        results = []
        for case in cases:
            actual, ms = self._generate(case.prompt)
            score, reason = self.judge.score(case.prompt, case.expected, actual)
            results.append(EvalResult(
                case_id=case.case_id, prompt=case.prompt, expected=case.expected,
                actual=actual, score=score, passed=score >= self.threshold,
                latency_ms=ms, model=self.model, reason=reason))
            print(f"  {'✓' if score >= self.threshold else '✗'} {case.case_id} "
                  f"score={score:.2f} ({ms}ms)")

        passed     = sum(1 for r in results if r.passed)
        avg_score  = sum(r.score for r in results) / len(results) if results else 0
        avg_lat    = sum(r.latency_ms for r in results) / len(results) if results else 0
        return EvalRun(run_id=run_id, model=self.model, cases=len(results),
                       passed=passed, avg_score=avg_score, avg_latency_ms=avg_lat,
                       results=results)


def _save_run(run: EvalRun):
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    p = EVALS_DIR / f"{run.run_id}.json"
    p.write_text(json.dumps({
        "run_id": run.run_id, "model": run.model, "ts": run.ts,
        "cases": run.cases, "passed": run.passed,
        "avg_score": run.avg_score, "avg_latency_ms": run.avg_latency_ms,
        "results": [{
            "case_id": r.case_id, "score": r.score, "passed": r.passed,
            "latency_ms": r.latency_ms, "reason": r.reason,
            "actual": r.actual[:500]
        } for r in run.results]
    }, indent=2))
    return str(p)


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_eval_run(suite_path: str, api_key: str, model: str,
                 judge_model: str = "zc-xxx",
                 threshold: float = 0.7, output: Optional[str] = None):
    """Run an eval suite (JSON file of [{case_id, prompt, expected, tags}])"""
    data  = json.loads(Path(suite_path).read_text())
    cases = [EvalCase(**c) for c in data]
    print(f"Running {len(cases)} eval cases against {model} …\n")
    runner = EvalRunner(api_key, model, judge_model, threshold)
    run    = runner.run(cases)
    print(f"\n{run.summary()}")
    path = _save_run(run)
    print(f"Results saved → {path}")
    if output:
        Path(output).write_text(json.dumps(run.results[0].__dict__ if run.results else {}, indent=2))


def cmd_eval_compare(suite_path: str, model_a: str, model_b: str,
                     api_key: str, judge_model: str = "zc-xxx"):
    """Compare two models head-to-head on the same eval suite."""
    data  = json.loads(Path(suite_path).read_text())
    cases = [EvalCase(**c) for c in data]
    print(f"Comparing {model_a}  vs  {model_b}  on {len(cases)} cases …\n")
    for m in [model_a, model_b]:
        print(f"── {m} ──")
        runner = EvalRunner(api_key, m, judge_model)
        run    = runner.run(cases)
        print(f"   {run.summary()}\n")


def cmd_eval_list():
    if not EVALS_DIR.exists(): print("No eval runs found."); return
    for p in sorted(EVALS_DIR.glob("*.json"), reverse=True)[:20]:
        try:
            d = json.loads(p.read_text())
            print(f"  [{d['run_id']}] {d['ts'][:16]}  model={d['model']}  "
                  f"{d['passed']}/{d['cases']}  avg={d['avg_score']:.2f}")
        except Exception: pass


def cmd_eval_scaffold(output: str):
    """Write a starter eval suite file."""
    suite = [
        {"case_id": "greet_01", "prompt": "Say hello in one sentence.",
         "expected": "Response is a friendly single-sentence greeting."},
        {"case_id": "code_01",  "prompt": "Write a Python function to reverse a string.",
         "expected": "Response contains a working Python function that reverses a string."},
    ]
    Path(output).write_text(json.dumps(suite, indent=2))
    print(f"✓ Starter eval suite written to {output}")