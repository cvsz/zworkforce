"""
zc_workflow.py — Declarative multi-step pipelines defined in YAML/JSON.
Each step is a named task with an instruction, optional depends_on list,
and optional output_var that saves the response for use in later steps.
AI Model Coder CLI v1.10.0

Example YAML:
  name: "Refactor + Document"
  model: zc-xxx
  steps:
    - id: refactor
      instruction: "Refactor this code for readability: {{input}}"
    - id: tests
      instruction: "Write unit tests for:\n{{refactor}}"
      depends_on: [refactor]
    - id: docs
      instruction: "Write a docstring for:\n{{refactor}}"
      depends_on: [refactor]
    - id: summary
      instruction: "Summarise what changed:\nCode: {{refactor}}\nTests: {{tests}}"
      depends_on: [refactor, tests]
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


@dataclass
class WorkflowStep:
    step_id:    str
    instruction: str
    depends_on: list[str] = field(default_factory=list)
    model:      Optional[str] = None
    max_tokens: int = 2048


@dataclass
class Workflow:
    name:  str
    steps: list[WorkflowStep]
    model: str = "claude-sonnet-5"


@dataclass
class StepResult:
    step_id:    str
    output:     str
    latency_ms: int
    status:     str = "ok"   # "ok" | "error"
    error:      Optional[str] = None


@dataclass
class WorkflowRun:
    workflow:  str
    results:   list[StepResult]
    variables: dict[str, str]
    elapsed_s: float
    ts:        str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        lines = [f"# Workflow Run: {self.workflow}", f"_Completed: {self.ts}_\n"]
        for r in self.results:
            icon = "✓" if r.status == "ok" else "✗"
            lines.append(f"## {icon} {r.step_id}  ({r.latency_ms}ms)\n{r.output}\n")
        return "\n".join(lines)


def _load(path: str) -> dict:
    text = Path(path).read_text()
    if path.endswith((".yml", ".yaml")):
        if not _HAS_YAML:
            raise RuntimeError("PyYAML not installed — run: pip install pyyaml --break-system-packages")
        return _yaml.safe_load(text)
    return json.loads(text)


def _parse(d: dict) -> Workflow:
    steps = [WorkflowStep(
        step_id    = s["id"],
        instruction= s["instruction"],
        depends_on = s.get("depends_on", []),
        model      = s.get("model"),
        max_tokens = s.get("max_tokens", 2048),
    ) for s in d.get("steps", [])]
    return Workflow(name=d.get("name","Untitled"), steps=steps,
                   model=d.get("model","zc-xxx"))


def _fill(template: str, variables: dict[str, str]) -> str:
    def replace(m):
        key = m.group(1).strip()
        return variables.get(key, f"{{{{ {key} }}}}")
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", replace, template)


def run_workflow(wf: Workflow, api_key: str, initial_vars: Optional[dict[str, str]] = None,
                 verbose: bool = False) -> WorkflowRun:
    client    = anthropic.Anthropic(api_key=api_key)
    variables = dict(initial_vars or {})
    results: list[StepResult] = []
    completed: set = set()
    t_start = time.time()

    # Topological execution (simple ready-queue loop; no true parallelism here)
    pending = list(wf.steps)
    max_iters = len(pending) ** 2 + 10
    iters = 0
    while pending and iters < max_iters:
        iters += 1
        ready = [s for s in pending if all(d in completed for d in s.depends_on)]
        if not ready:
            remaining_ids = [s.step_id for s in pending]
            for s in pending:
                results.append(StepResult(step_id=s.step_id, output="",
                    latency_ms=0, status="error",
                    error=f"Dependency deadlock — remaining: {remaining_ids}"))
            break
        for step in ready:
            pending.remove(step)
            instruction = _fill(step.instruction, variables)
            if verbose: print(f"  → {step.step_id} …", end="", flush=True)
            t0 = time.time()
            try:
                resp = client.messages.create(
                    model=step.model or wf.model, max_tokens=step.max_tokens,
                    messages=[{"role": "user", "content": instruction}])
                block = resp.content[0]
                if block.type == "text":
                    output = block.text
                else:
                    output = str(block)
                ms     = int((time.time() - t0) * 1000)
                variables[step.step_id] = output
                completed.add(step.step_id)
                results.append(StepResult(step_id=step.step_id, output=output, latency_ms=ms))
                if verbose: print(f" {ms}ms ✓")
            except Exception as e:
                ms = int((time.time() - t0) * 1000)
                results.append(StepResult(step_id=step.step_id, output="",
                    latency_ms=ms, status="error", error=str(e)))
                completed.add(step.step_id)
                if verbose: print(f" ERROR: {e}")

    return WorkflowRun(workflow=wf.name, results=results, variables=variables,
                       elapsed_s=round(time.time() - t_start, 2))


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_workflow_run(path: str, api_key: str, input_text: str = "",
                     output: Optional[str] = None, verbose: bool = True):
    wf  = _parse(_load(path))
    print(f"⚙  Running workflow '{wf.name}' ({len(wf.steps)} steps) …\n")
    run = run_workflow(wf, api_key, initial_vars={"input": input_text}, verbose=verbose)
    md  = run.to_markdown()
    if output:
        Path(output).write_text(md)
        print(f"\n✓ Output → {output}")
    else:
        print("\n" + md)
    print(f"Elapsed: {run.elapsed_s}s")


def cmd_workflow_scaffold(output: str):
    sample = {
        "name": "Example Workflow",
        "model": "zc-xxx",
        "steps": [
            {"id": "draft",   "instruction": "Write a short essay about: {{input}}"},
            {"id": "improve", "instruction": "Improve this essay:\n{{draft}}",
             "depends_on": ["draft"]},
        ]
    }
    Path(output).write_text(json.dumps(sample, indent=2))
    print(f"✓ Starter workflow saved to {output}")
