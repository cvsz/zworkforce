from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from typing import Any

from .agent_handoff import AgentHandoffProtocol, AgentHandoffError
from .db import TERMINAL_STATUSES, utcnow
from .evaluator import EvaluationError, evaluate, validate_criteria
from .providers import ProviderError
from .router import ModelRouter
from .security import canonical_request_hash, redact
from .skills import verify_manifest
from .tools import TOOL_DEFINITIONS, ToolError, ToolExecutor, is_mutating_tool, tool_schemas


class Engine:
    def __init__(self, settings, db, provider):
        self.settings = settings
        self.db = db
        self.provider = provider
        self.router = ModelRouter()
        self.tools = ToolExecutor(settings, db)
        self.handoff = AgentHandoffProtocol()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start_workers(self, count: int | None = None, prefix: str = "embedded") -> int:
        count = self.settings.embedded_workers if count is None else max(0, int(count))
        for index in range(count):
            worker_id = f"{prefix}-{index + 1}-{uuid.uuid4().hex[:8]}"
            thread = threading.Thread(target=self.worker_loop, args=(worker_id,), name=f"zworkforce-{worker_id}", daemon=True)
            thread.start()
            self._threads.append(thread)
        return count

    def shutdown(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=2)
        self._threads.clear()

    def recover(self) -> dict[str, int]:
        return self.db.requeue_expired_leases()

    def worker_loop(self, worker_id: str, once: bool = False) -> int:
        processed = 0
        last_recovery = 0.0
        while not self._stop.is_set():
            if time.monotonic() - last_recovery >= max(5, self.settings.lease_seconds // 2):
                self.db.requeue_expired_leases()
                last_recovery = time.monotonic()
            task = self.db.claim_next_task(worker_id, self.settings.lease_seconds)
            if task:
                processed += 1
                self._execute_claimed(task, worker_id)
                if once:
                    return processed
                continue
            if once:
                return processed
            self._stop.wait(self.settings.worker_poll_ms / 1000)
        return processed

    def submit(
        self,
        tenant_id: str,
        agent_id: str,
        prompt: str,
        *,
        actor: str,
        mutating: bool = False,
        tier_override: str | None = None,
        parent_task_id: str | None = None,
        depth: int = 0,
        idempotency_key: str | None = None,
        priority: int = 0,
        success_criteria: list[dict[str, Any]] | None = None,
        max_attempts: int | None = None,
    ) -> tuple[dict[str, Any], bool]:
        agent = self.db.get_agent(tenant_id, agent_id)
        if not agent or not agent["enabled"]:
            raise ValueError("agent not found or disabled")
        prompt = str(prompt)
        if not prompt.strip():
            raise ValueError("prompt is required")
        if len(prompt.encode("utf-8")) > self.settings.max_request_bytes:
            raise ValueError("prompt exceeds request size limit")
        if depth > self.settings.max_delegation_depth:
            raise ValueError("delegation depth exceeds platform limit")
        if parent_task_id:
            parent = self.db.get_task(tenant_id, parent_task_id)
            if not parent:
                raise ValueError("parent task not found in tenant")
            if depth != int(parent["depth"]) + 1:
                raise ValueError("invalid delegation depth")
        if violation := self.db.budget_violation(tenant_id, agent, self.settings.global_daily_budget_credits):
            raise ValueError(violation)
        allowed_tools, _, _ = self._agent_policy(tenant_id, agent)
        tier, rationale = self.router.choose(prompt, agent["default_tier"], mutating, tier_override, tool_count=len(allowed_tools))
        provider_name, model = self.provider.preview(tier)
        required = int(agent.get("required_approvals", 1)) if mutating and agent.get("requires_approval_for_mutations") else 0
        required = max(0, min(required, 3))
        criteria = success_criteria or [{"type": "non_empty"}]
        validate_criteria(criteria)
        status = "waiting_approval" if required else "queued"
        task_id = str(uuid.uuid4())
        payload_for_hash = {
            "agent_id": agent_id,
            "prompt": prompt,
            "mutating": bool(mutating),
            "tier_override": tier_override,
            "parent_task_id": parent_task_id,
            "depth": depth,
            "priority": int(priority),
            "success_criteria": criteria,
        }
        t = {
            "id": task_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "prompt": prompt,
            "created_by": actor,
            "status": status,
            "tier": tier,
            "model": model,
            "provider_name": provider_name,
            "mutating": bool(mutating),
            "parent_task_id": parent_task_id,
            "depth": depth,
            "required_approvals": required,
            "priority": max(-100, min(int(priority), 100)),
            "max_attempts": max(1, min(int(max_attempts or self.settings.max_attempts), 10)),
            "success_criteria": criteria,
        }
        task, created = self.db.create_task(t, idempotency_key, canonical_request_hash(payload_for_hash))
        if created:
            self.db.audit(tenant_id, actor, "task.create", "task", task_id, {"agent_id": agent_id, "tier": tier, "mutating": mutating, "router": rationale, "required_approvals": required})
        return task, created

    def approve(self, tenant_id: str, task_id: str, actor: str, comment: str = "") -> dict[str, Any]:
        task = self.db.approval_decision(tenant_id, task_id, actor, "approve", comment)
        self.db.audit(tenant_id, actor, "task.approve", "task", task_id, {"comment": comment[:500]})
        return task

    def reject(self, tenant_id: str, task_id: str, actor: str, comment: str = "") -> dict[str, Any]:
        task = self.db.approval_decision(tenant_id, task_id, actor, "reject", comment)
        self.db.audit(tenant_id, actor, "task.reject", "task", task_id, {"comment": comment[:500]})
        return task

    def cancel(self, tenant_id: str, task_id: str, actor: str) -> dict[str, Any]:
        task = self.db.get_task(tenant_id, task_id)
        if not task:
            raise ValueError("task not found")
        if task["status"] in TERMINAL_STATUSES:
            return task
        if task["status"] in {"queued", "waiting_approval"}:
            self.db.update_task(task_id, status="canceled", cancel_requested=1, finished_at=utcnow(), lease_owner=None, lease_expires_at=None)
        else:
            self.db.update_task(task_id, cancel_requested=1)
        self.db.task_event(tenant_id, task_id, "cancel_requested", actor)
        self.db.audit(tenant_id, actor, "task.cancel", "task", task_id)
        return self.db.get_task(tenant_id, task_id) or {}

    def retry(self, tenant_id: str, task_id: str, actor: str) -> dict[str, Any]:
        task = self.db.get_task(tenant_id, task_id)
        if not task:
            raise ValueError("task not found")
        if task["status"] not in {"failed", "dead_letter"}:
            raise ValueError("only failed or dead-letter tasks can be retried")
        self.db.update_task(task_id, status="queued", attempt=0, error=None, cancel_requested=0, run_after=utcnow(), finished_at=None, lease_owner=None, lease_expires_at=None, heartbeat_at=None)
        self.db.task_event(tenant_id, task_id, "manual_retry", actor)
        self.db.audit(tenant_id, actor, "task.retry", "task", task_id)
        return self.db.get_task(tenant_id, task_id) or {}

    def _agent_policy(self, tenant_id: str, agent: dict[str, Any]) -> tuple[set[str], set[str], str]:
        allowed = {name for name in (agent.get("allowed_tools") or []) if name in TOOL_DEFINITIONS}
        approval = {name for name in (agent.get("approval_tools") or []) if name in TOOL_DEFINITIONS}
        prompt_append: list[str] = []
        for skill_id in agent.get("skill_ids") or []:
            skill = self.db.get_skill(tenant_id, str(skill_id))
            if not skill or not skill.get("enabled"):
                continue
            manifest = skill.get("manifest") or {}
            valid = verify_manifest(manifest, skill.get("signature", ""), self.settings.skill_signing_key, self.settings.env == "production")
            if not valid:
                continue
            allowed.update(name for name in manifest.get("allowed_tools", []) if name in TOOL_DEFINITIONS)
            if manifest.get("system_prompt_append"):
                prompt_append.append(str(manifest["system_prompt_append"]))
        if int(agent.get("max_subagents", 0)) <= 0:
            allowed.discard("agent_delegate")
        return allowed, approval, "\n".join(prompt_append)

    def _execute_claimed(self, task: dict[str, Any], worker_id: str) -> None:
        tenant_id, task_id = task["tenant_id"], task["id"]
        agent = self.db.get_agent(tenant_id, task["agent_id"])
        if not agent:
            self._fail_terminal(task, "agent was deleted or is unavailable")
            return
        if violation := self.db.budget_violation(tenant_id, agent, self.settings.global_daily_budget_credits):
            self._fail_terminal(task, violation)
            return
        allowed_tools, approval_tools, skill_prompt = self._agent_policy(tenant_id, agent)
        system = (agent.get("system_prompt") or f"You are {agent['name']} in department {agent['department']}.")
        system += "\nUse only the tools exposed to you. Keep work bounded. Never claim a tool action succeeded unless its result confirms success."
        if skill_prompt:
            system += "\n\nSigned skill instructions:\n" + skill_prompt
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": task["prompt"]}]
        schemas = tool_schemas(allowed_tools)
        total_in = total_cache = total_out = 0
        total_cost = 0.0
        tier = task["tier"]
        delegated = 0
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(target=self._heartbeat_loop, args=(task_id, worker_id, heartbeat_stop), daemon=True)
        heartbeat.start()
        consecutive_tool_failures = 0
        identical_call_counts: dict[str, int] = {}
        max_identical = max(1, getattr(self.settings, "doom_loop_max_identical_calls", 3))
        max_failures = max(1, getattr(self.settings, "doom_loop_max_consecutive_failures", 5))

        try:
            for iteration in range(1, int(agent["max_iterations"]) + 1):
                current = self.db.get_task(tenant_id, task_id) or task
                if current.get("cancel_requested"):
                    self.db.update_task(task_id, status="canceled", iterations=iteration - 1, finished_at=utcnow(), lease_owner=None, lease_expires_at=None, heartbeat_at=None)
                    self.db.task_event(tenant_id, task_id, "canceled", "runtime")
                    return
                if violation := self.db.budget_violation(tenant_id, agent, self.settings.global_daily_budget_credits):
                    raise RuntimeError(violation)
                result = self.provider.chat(tier, messages, schemas)
                turn_cost = self._cost(tier, result.usage.input_tokens, result.usage.cached_tokens, result.usage.output_tokens)
                total_in += result.usage.input_tokens
                total_cache += result.usage.cached_tokens
                total_out += result.usage.output_tokens
                total_cost += turn_cost
                task_for_usage = dict(task, tier=tier)
                self.db.record_usage(task_for_usage, result.provider_name, result.model, result.usage.input_tokens, result.usage.cached_tokens, result.usage.output_tokens, turn_cost)
                self.db.update_task(task_id, tier=tier, model=result.model, provider_name=result.provider_name, input_tokens=total_in, cached_tokens=total_cache, output_tokens=total_out, cost_credits=total_cost, iterations=iteration)
                if total_cost > float(agent["max_cost_credits"]):
                    raise RuntimeError(f"task budget exceeded agent max_cost_credits={agent['max_cost_credits']}")
                assistant_message = result.raw_message or {"role": "assistant", "content": result.content}
                messages.append(assistant_message)
                if not result.tool_calls:
                    content = (result.content or "").strip()
                    if not content:
                        next_tier = self.router.escalate(tier)
                        if next_tier:
                            self.db.task_event(tenant_id, task_id, "tier_escalated", "runtime", {"from": tier, "to": next_tier, "reason": "empty_response"})
                            tier = next_tier
                            continue
                        raise RuntimeError("provider returned an empty response at highest tier")
                    outcome_status, outcome_score, outcome_details = evaluate(content, task.get("success_criteria"))
                    self.db.update_task(
                        task_id,
                        status="succeeded",
                        result=content,
                        input_tokens=total_in,
                        cached_tokens=total_cache,
                        output_tokens=total_out,
                        cost_credits=total_cost,
                        iterations=iteration,
                        outcome_status=outcome_status,
                        outcome_score=outcome_score,
                        outcome_details_json=json.dumps(outcome_details, separators=(",", ":"), ensure_ascii=False),
                        finished_at=utcnow(),
                        lease_owner=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                    )
                    self.db.task_event(tenant_id, task_id, "succeeded", "runtime", {"tier": tier, "provider": result.provider_name, "model": result.model, "cost_credits": total_cost, "outcome_status": outcome_status, "outcome_score": outcome_score})
                    self.db.audit(tenant_id, "runtime", "task.succeed", "task", task_id, {"tier": tier, "provider": result.provider_name, "cost_credits": total_cost, "iterations": iteration, "outcome_status": outcome_status})
                    return
                for call in result.tool_calls:
                    current = self.db.get_task(tenant_id, task_id) or task
                    if current.get("cancel_requested"):
                        self.db.update_task(task_id, status="canceled", finished_at=utcnow(), lease_owner=None, lease_expires_at=None, heartbeat_at=None)
                        return

                    # Doom loop detection: Track identical tool call signatures
                    call_sig = json.dumps({"name": call.name, "args": call.arguments}, sort_keys=True, default=str)
                    identical_count = identical_call_counts.get(call_sig, 0) + 1
                    identical_call_counts[call_sig] = identical_count
                    if identical_count > max_identical:
                        self.db.task_event(tenant_id, task_id, "doom_loop_detected", "runtime", {"tool": call.name, "identical_count": identical_count})
                        raise RuntimeError(f"doom-loop detected: tool {call.name!r} invoked {identical_count} times with identical arguments")

                    if call.name not in allowed_tools:
                        tool_result = {"error": f"tool {call.name!r} is not granted to this agent"}
                    elif call.name == "agent_delegate":
                        if delegated >= int(agent["max_subagents"]):
                            tool_result = {"error": "max_subagents reached"}
                        elif int(task["depth"]) >= self.settings.max_delegation_depth:
                            tool_result = {"error": "maximum delegation depth reached"}
                        else:
                            child_target = str(call.arguments.get("agent_id", ""))
                            child_mutating = bool(call.arguments.get("mutating", False))
                            try:
                                validated_args = self.handoff.validate_handoff(
                                    source_agent_id=str(task["agent_id"]),
                                    target_agent_id=child_target,
                                    arguments=call.arguments,
                                    is_mutating=child_mutating,
                                )
                                delegated += 1
                                child, _ = self.submit(
                                    tenant_id,
                                    child_target,
                                    str(validated_args.get("prompt", "")),
                                    actor=f"agent:{task['agent_id']}",
                                    mutating=child_mutating,
                                    parent_task_id=task_id,
                                    depth=int(task["depth"]) + 1,
                                )
                                tool_result = {"task_id": child["id"], "status": child["status"], "requires_approval": bool(child.get("required_approvals"))}
                            except AgentHandoffError as hexc:
                                tool_result = {"error": f"agent handoff rejected: {str(hexc)}"}
                    else:
                        mutating_tool = is_mutating_tool(call.name)
                        if mutating_tool and not bool(task.get("mutating")):
                            tool_result = {"error": "mutating tool denied because task was not declared mutating"}
                        elif mutating_tool and int(task.get("required_approvals", 0)) > 0 and not current.get("approved_at"):
                            tool_result = {"error": "mutating tool denied until required approvals are complete"}
                        elif call.name in approval_tools and int(task.get("required_approvals", 0)) > 0 and not current.get("approved_at"):
                            tool_result = {"error": "tool policy requires approval"}
                        else:
                            tool_result = self._execute_tool(task, call.name, call.arguments)

                    # Doom loop detection: Track consecutive tool execution failures
                    if isinstance(tool_result, dict) and "error" in tool_result:
                        consecutive_tool_failures += 1
                        if consecutive_tool_failures >= max_failures:
                            self.db.task_event(tenant_id, task_id, "doom_loop_detected", "runtime", {"consecutive_failures": consecutive_tool_failures, "last_error": str(tool_result["error"])})
                            raise RuntimeError(f"doom-loop detected: {consecutive_tool_failures} consecutive tool execution failures (last error: {tool_result['error']})")
                    else:
                        consecutive_tool_failures = 0

                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(tool_result, ensure_ascii=False, default=str)})
            raise RuntimeError("max_iterations reached before completion")
        except ProviderError as exc:
            latest = self.db.get_task(tenant_id, task_id) or task
            if latest.get("cancel_requested"):
                self.db.update_task(task_id, status="canceled", error=str(exc), finished_at=utcnow(), lease_owner=None, lease_expires_at=None, heartbeat_at=None)
                return
            if exc.retryable:
                delay = min(self.settings.retry_base_seconds * (2 ** max(0, int(latest.get("attempt", 1)) - 1)), 300)
                status = self.db.release_for_retry(latest, str(exc), delay)
                self.db.audit(tenant_id, "runtime", f"task.{status}", "task", task_id, {"error": str(exc)[:500], "attempt": latest.get("attempt")})
            else:
                self._fail_terminal(latest, str(exc))
        except (RuntimeError, EvaluationError, ValueError, OSError) as exc:
            self._fail_terminal(self.db.get_task(tenant_id, task_id) or task, str(exc))
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)

    def _execute_tool(self, task: dict[str, Any], name: str, args: dict[str, Any]) -> Any:
        started = time.monotonic()
        success = False
        error = ""
        try:
            result = self.tools.execute(name, args, tenant_id=task["tenant_id"], agent_id=task["agent_id"], actor=f"agent:{task['agent_id']}")
            success = True
            return result
        except (ToolError, OSError, ValueError, subprocess.SubprocessError) as exc:
            error = str(exc)
            return {"error": error}
        finally:
            self.db.record_tool_event(
                task["tenant_id"],
                task["id"],
                task["agent_id"],
                name,
                is_mutating_tool(name),
                success,
                (time.monotonic() - started) * 1000,
                redact(args),
                error,
            )

    def _heartbeat_loop(self, task_id: str, worker_id: str, stop: threading.Event) -> None:
        interval = min(self.settings.lease_heartbeat_seconds, max(2, self.settings.lease_seconds // 2))
        while not stop.wait(interval):
            if not self.db.heartbeat(task_id, worker_id, self.settings.lease_seconds):
                return

    def _fail_terminal(self, task: dict[str, Any], error: str) -> None:
        status = "canceled" if task.get("cancel_requested") else "failed"
        self.db.update_task(task["id"], status=status, error=error[:4000], finished_at=utcnow(), lease_owner=None, lease_expires_at=None, heartbeat_at=None)
        self.db.task_event(task["tenant_id"], task["id"], status, "runtime", {"error": error[:500]})
        self.db.audit(task["tenant_id"], "runtime", f"task.{status}", "task", task["id"], {"error": error[:500]})

    def _cost(self, tier: str, inp: int, cached: int, out: int) -> float:
        r = self.settings.rates[tier]
        uncached = max(0, int(inp) - int(cached))
        return ((uncached * r.input) + (max(0, int(cached)) * r.cached) + (max(0, int(out)) * r.output)) / 1_000_000
