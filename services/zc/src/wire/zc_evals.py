"""
zc_evals.py — Evaluation Harness
AI Model Coder CLI v1.9.1

Run structured test suites against zAICoder: assert on output content,
compare two model versions, track pass-rates over time, and output
results as JSON or a terminal table.

CLI flags:
  --eval FILE             Run an eval suite from a JSON/YAML file
  --eval-create FILE      Scaffold a blank eval suite file at FILE
  --eval-compare          With --eval: compare --model vs --model2 on all test cases
  --eval-output FILE      Write eval results to FILE as JSON
  --eval-verbose          Print each test case result in full
"""

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import anthropic

from wire.utils import sampling_kwargs


@dataclass
class EvalCase:
    id: str
    prompt: str
    system: str = ""
    expected_contains: list[str] = field(default_factory=list)      # all must be present
    expected_not_contains: list[str] = field(default_factory=list)  # none must be present
    expected_json: bool = False                                       # output must parse as JSON
    expected_regex: str = ""                                          # regex must match
    max_tokens: int = 2048
    temperature: float = 0.0


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    response: str
    latency_seconds: float
    failures: list[str] = field(default_factory=list)
    model: str = ""


@dataclass
class EvalSuiteResult:
    suite_name: str
    model: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    total_time: float
    results: list[EvalResult] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["results"] = [asdict(r) for r in self.results]
        return d


def load_suite(path: str) -> tuple[str, list[EvalCase]]:
    with open(path) as f:
        raw = json.load(f)
    name = raw.get("name", Path(path).stem)
    cases: list[EvalCase] = []
    for c in raw.get("cases", []):
        cases.append(EvalCase(
            id=c.get("id", f"case_{len(cases)+1}"),
            prompt=c["prompt"],
            system=c.get("system", ""),
            expected_contains=c.get("expected_contains", []),
            expected_not_contains=c.get("expected_not_contains", []),
            expected_json=c.get("expected_json", False),
            expected_regex=c.get("expected_regex", ""),
            max_tokens=c.get("max_tokens", 2048),
            temperature=c.get("temperature", 0.0),
        ))
    return name, cases


def run_case(case: EvalCase, client: anthropic.Anthropic,
             model: str) -> EvalResult:
    messages = [{"role": "user", "content": case.prompt}]
    kwargs: dict[str, Any] = {
        "model": model, "max_tokens": case.max_tokens,
        **sampling_kwargs(model, temperature=case.temperature), "messages": messages,
    }
    if case.system:
        kwargs["system"] = case.system

    t0 = time.time()
    resp = client.messages.create(**kwargs)
    latency = round(time.time() - t0, 3)
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))

    failures = []
    for phrase in case.expected_contains:
        if phrase.lower() not in text.lower():
            failures.append(f"missing required phrase: {phrase!r}")
    for phrase in case.expected_not_contains:
        if phrase.lower() in text.lower():
            failures.append(f"contains forbidden phrase: {phrase!r}")
    if case.expected_json:
        try:
            json.loads(text)
        except json.JSONDecodeError:
            failures.append("output is not valid JSON")
    if case.expected_regex:
        if not re.search(case.expected_regex, text):
            failures.append(f"regex did not match: {case.expected_regex!r}")

    return EvalResult(
        case_id=case.id, passed=not failures,
        response=text, latency_seconds=latency,
        failures=failures, model=model,
    )


def run_suite(path: str, api_key: str, model: str,
              verbose: bool = False) -> EvalSuiteResult:
    name, cases = load_suite(path)
    client = anthropic.Anthropic(api_key=api_key)
    results = []
    t0 = time.time()

    for case in cases:
        result = run_case(case, client, model)
        results.append(result)
        icon = "\033[92m✓\033[0m" if result.passed else "\033[91m✗\033[0m"
        print(f"  {icon} {result.case_id:<30} {result.latency_seconds}s")
        if verbose and not result.passed:
            for f in result.failures:
                print(f"      \033[91m! {f}\033[0m")
            print(f"      Response: {result.response[:200]}...")

    passed = sum(1 for r in results if r.passed)
    return EvalSuiteResult(
        suite_name=name, model=model, total=len(cases),
        passed=passed, failed=len(cases) - passed,
        pass_rate=round(passed / max(1, len(cases)) * 100, 1),
        total_time=round(time.time() - t0, 2),
        results=results,
    )


def scaffold_suite(path: str) -> str:
    template = {
        "name": "My Eval Suite",
        "cases": [
            {
                "id": "hello_world",
                "prompt": "Say hello in exactly three words.",
                "expected_contains": ["hello"],
                "expected_not_contains": ["I cannot"],
            },
            {
                "id": "json_output",
                "prompt": "Return a JSON object with keys 'x' and 'y' both set to 1.",
                "expected_json": True,
                "expected_contains": ["x", "y"],
            },
        ],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(template, f, indent=2)
    return path


def cmd_eval(suite_path: str, api_key: str, model: str,
             model2: Optional[str] = None, output_path: Optional[str] = None,
             verbose: bool = False):
    print(f"\n\033[94mRunning eval suite: {suite_path}\033[0m  model={model}")
    suite_result = run_suite(suite_path, api_key, model, verbose)

    print(f"\n  Pass rate: \033[1m{suite_result.pass_rate}%\033[0m "
          f"({suite_result.passed}/{suite_result.total}) in {suite_result.total_time}s")

    if model2:
        print(f"\n\033[94mComparing with model: {model2}\033[0m")
        suite_result2 = run_suite(suite_path, api_key, model2, verbose)
        print(f"\n  {model:<35} {suite_result.pass_rate}% ({suite_result.passed}/{suite_result.total})")
        print(f"  {model2:<35} {suite_result2.pass_rate}% ({suite_result2.passed}/{suite_result2.total})")

    if output_path:
        with open(output_path, "w") as f:
            json.dump(suite_result.to_dict(), f, indent=2)
        print(f"\n  Results saved to {output_path}")