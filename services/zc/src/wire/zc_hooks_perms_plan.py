"""
zc_hooks.py — Lifecycle hooks (pre/post tool-use, session start/end).
zc_permissions.py — Fine-grained allow/deny/ask ACL for tool names.
zc_plan_mode.py — Propose a numbered plan, approve, then execute.
AI Model Coder CLI v1.10.0
"""

# ═══════════════════════════════════════════════════════════════════════
# HOOKS
# ═══════════════════════════════════════════════════════════════════════

import fnmatch
import json
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

HOOKS_FILE = Path.home() / ".ai-coder" / "hooks.json"
PERMS_FILE = Path.home() / ".ai-coder" / "permissions.json"


class HookEvent(Enum):
    PRE_TOOL_USE  = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    SESSION_START = "session_start"
    SESSION_END   = "session_end"


@dataclass
class Hook:
    event:      HookEvent
    command:    str
    tool_match: Optional[str] = None
    description: str = ""

    def to_dict(self): return {"event": self.event.value, "command": self.command,
                               "tool_match": self.tool_match, "description": self.description}
    @staticmethod
    def from_dict(d): return Hook(event=HookEvent(d["event"]), command=d["command"],
                                  tool_match=d.get("tool_match"), description=d.get("description",""))


@dataclass
class HookResult:
    hook:       Hook
    returncode: int
    stdout:     str
    stderr:     str
    blocked:    bool = False


class HookManager:
    def __init__(self):
        self.hooks: list[Hook] = []
        self._load()

    def _load(self):
        if HOOKS_FILE.exists():
            try: self.hooks = [Hook.from_dict(d) for d in json.loads(HOOKS_FILE.read_text())]
            except Exception as _e: pass

    def save(self):
        HOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        HOOKS_FILE.write_text(json.dumps([h.to_dict() for h in self.hooks], indent=2))

    def add(self, event: HookEvent, command: str, tool_match: Optional[str] = None,
            description: str = ""):
        self.hooks.append(Hook(event=event, command=command, tool_match=tool_match,
                              description=description))
        self.save()

    def remove(self, idx: int) -> bool:
        if 0 <= idx < len(self.hooks):
            del self.hooks[idx]; self.save(); return True
        return False

    def fire(self, event: HookEvent, tool_name: Optional[str] = None) -> list[HookResult]:
        env = {**os.environ}
        if tool_name: env["AI_CODER_TOOL_NAME"] = tool_name
        env["AI_CODER_HOOK_EVENT"] = event.value
        results = []
        for h in [h for h in self.hooks if h.event == event]:
            if h.tool_match and tool_name and h.tool_match not in tool_name: continue
            try:
                import shlex
                cmd_args = shlex.split(h.command) if isinstance(h.command, str) else h.command
                p = subprocess.run(cmd_args, shell=False, capture_output=True,
                                   text=True, timeout=30, env=env)
                blocked = (event == HookEvent.PRE_TOOL_USE and p.returncode != 0)
                results.append(HookResult(hook=h, returncode=p.returncode,
                                         stdout=p.stdout, stderr=p.stderr, blocked=blocked))
            except subprocess.TimeoutExpired:
                results.append(HookResult(hook=h, returncode=-1, stdout="",
                                         stderr="timeout", blocked=(event == HookEvent.PRE_TOOL_USE)))
        return results

    def guarded_call(self, tool_name: str, fn: Callable, *args, **kwargs) -> Any:
        pre = self.fire(HookEvent.PRE_TOOL_USE, tool_name)
        blocked = [r for r in pre if r.blocked]
        if blocked:
            reasons = "; ".join(r.stderr.strip() or r.hook.command for r in blocked)
            raise PermissionError(f"Tool '{tool_name}' blocked by hook: {reasons}")
        result = fn(*args, **kwargs)
        self.fire(HookEvent.POST_TOOL_USE, tool_name)
        return result


def cmd_hooks_add(event: str, command: str, tool_match: Optional[str] = None):
    hm = HookManager()
    hm.add(HookEvent(event), command, tool_match)
    print(f"✓ Hook registered for {event}: {command}")

def cmd_hooks_list():
    hm = HookManager()
    if not hm.hooks: print("No hooks registered."); return
    for i, h in enumerate(hm.hooks):
        match = f" [match={h.tool_match}]" if h.tool_match else ""
        print(f"  {i}. [{h.event.value}]{match}  {h.command}")

def cmd_hooks_remove(idx: int):
    hm = HookManager()
    if hm.remove(idx): print(f"✓ Hook {idx} removed.")
    else: print(f"No hook at index {idx}")


# ═══════════════════════════════════════════════════════════════════════
# PERMISSIONS
# ═══════════════════════════════════════════════════════════════════════

class Decision(Enum):
    ALLOW = "allow"
    DENY  = "deny"
    ASK   = "ask"


@dataclass
class PermRule:
    pattern:  str
    decision: Decision
    reason:   str = ""

    def to_dict(self): return {"pattern": self.pattern, "decision": self.decision.value, "reason": self.reason}
    @staticmethod
    def from_dict(d): return PermRule(pattern=d["pattern"], decision=Decision(d["decision"]), reason=d.get("reason",""))


DEFAULT_RULES = [
    PermRule("read_*",    Decision.ALLOW, "Read-only"),
    PermRule("list_*",    Decision.ALLOW, "Listing is safe"),
    PermRule("git_status",Decision.ALLOW, "Read-only git"),
    PermRule("git_diff",  Decision.ALLOW, "Read-only git"),
    PermRule("delete_*",  Decision.ASK,   "Destructive"),
    PermRule("run_shell", Decision.ASK,   "Arbitrary execution"),
    PermRule("git_push",  Decision.ASK,   "Publishes changes"),
]


class PermissionEngine:
    def __init__(self):
        self.rules: list[PermRule] = []
        self._load()

    def _load(self):
        if PERMS_FILE.exists():
            try: self.rules = [PermRule.from_dict(d) for d in json.loads(PERMS_FILE.read_text())]
            except Exception: self.rules = list(DEFAULT_RULES)
        else:
            self.rules = list(DEFAULT_RULES)

    def save(self):
        PERMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PERMS_FILE.write_text(json.dumps([r.to_dict() for r in self.rules], indent=2))

    def add(self, pattern: str, decision: Decision, reason: str = ""):
        self.rules.insert(0, PermRule(pattern=pattern, decision=decision, reason=reason))
        self.save()

    def evaluate(self, tool_name: str) -> PermRule:
        for r in self.rules:
            if fnmatch.fnmatch(tool_name, r.pattern): return r
        return PermRule("*", Decision.ASK, "No matching rule")

    def is_allowed(self, tool_name: str, ask_cb: Optional[Callable] = None) -> bool:
        r = self.evaluate(tool_name)
        if r.decision == Decision.ALLOW: return True
        if r.decision == Decision.DENY:  return False
        return bool(ask_cb(r, tool_name)) if ask_cb else False


def cmd_perms_list():
    pe = PermissionEngine()
    print(f"{'Pattern':<25} {'Decision':<8} Reason")
    print("─" * 55)
    for r in pe.rules:
        print(f"  {r.pattern:<23} {r.decision.value:<8} {r.reason}")

def cmd_perms_add(pattern: str, decision: str, reason: str = ""):
    pe = PermissionEngine()
    pe.add(pattern, Decision(decision), reason)
    print(f"✓ Rule added: {pattern} → {decision}")


# ═══════════════════════════════════════════════════════════════════════
# PLAN MODE
# ═══════════════════════════════════════════════════════════════════════

import anthropic as _anthropic


@dataclass
class PlanStep:
    number:      int
    description: str
    result:      Optional[str] = None
    completed:   bool = False


@dataclass
class Plan:
    task:     str
    steps:    list[PlanStep]
    approved: bool = False

    def to_markdown(self) -> str:
        lines = [f"# Plan: {self.task}", ""]
        for s in self.steps:
            mark = "x" if s.completed else " "
            lines.append(f"- [{mark}] {s.number}. {s.description}")
        return "\n".join(lines)


class PlanModeAgent:
    def __init__(self, api_key: str, model: str = "zc-sonnet-4-6"):
        self.client = _anthropic.Anthropic(api_key=api_key)
        self.model  = model

    def _call(self, system: str, user: str, max_tokens: int = 2048) -> str:
        r = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, temperature=0.3,
            system=system, messages=[{"role":"user","content":user}])
        return str(getattr(r.content[0], "text", ""))

    def propose(self, task: str, context: str = "") -> Plan:
        raw = self._call("Output only valid JSON.",
            f"Break this task into 3–8 concrete, numbered steps. Return ONLY a JSON array of strings.\n"
            f"Task: {task}\n" + (f"Context:\n{context}" if context else ""))
        cleaned = raw.strip()
        if cleaned.startswith("```"): cleaned = "\n".join(cleaned.split("\n")[1:-1])
        try: descs = json.loads(cleaned)
        except Exception: descs = [l.lstrip("-· ").strip() for l in raw.splitlines() if l.strip()]
        return Plan(task=task, steps=[PlanStep(number=i+1, description=d) for i,d in enumerate(descs)])

    def execute_step(self, plan: Plan, number: int) -> PlanStep:
        if not plan.approved: raise PermissionError("Plan not approved")
        step = next((s for s in plan.steps if s.number == number), None)
        if not step: raise ValueError(f"Step {number} not found")
        prior = "\n".join(f"Step {s.number}: {s.result}" for s in plan.steps if s.completed and s.result)
        step.result = self._call("Execute the task step precisely.",
            f"Task: {plan.task}\nStep {step.number}: {step.description}\n"
            + (f"\nCompleted prior steps:\n{prior}" if prior else ""))
        step.completed = True; return step

    def execute_all(self, plan: Plan) -> Plan:
        for s in plan.steps:
            if not s.completed: self.execute_step(plan, s.number)
        return plan

    @staticmethod
    def approve(plan: Plan) -> Plan: plan.approved = True; return plan


def cmd_plan(task: str, api_key: str, model: str, context: str = "",
             execute: bool = False, output: Optional[str] = None):
    agent = PlanModeAgent(api_key, model)
    plan  = agent.propose(task, context)
    print(plan.to_markdown())
    if execute:
        PlanModeAgent.approve(plan)
        print("\nExecuting …\n")
        for step in plan.steps:
            print(f"  Step {step.number}: {step.description}")
            agent.execute_step(plan, step.number)
            print(f"  → {(step.result or '')[:200]}\n")
        if output:
            md = plan.to_markdown() + "\n\n" + "\n\n".join(
                f"## Step {s.number}\n{s.result or ''}" for s in plan.steps)
            Path(output).write_text(md)
            print(f"✓ Saved to {output}")
    else:
        print("\n(Not executed — re-run with --execute to approve and run.)")