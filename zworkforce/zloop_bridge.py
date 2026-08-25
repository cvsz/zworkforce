from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence
import hashlib
import json


class LoopPhase(str, Enum):
    DISCOVER = "DISCOVER"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    REVIEW = "REVIEW"
    REPAIR = "REPAIR"
    SHIPPED = "SHIPPED"
    HANDOFF = "HANDOFF"
    FAILED = "FAILED"


TERMINAL = {LoopPhase.SHIPPED, LoopPhase.HANDOFF, LoopPhase.FAILED}


@dataclass(frozen=True)
class LoopBudget:
    max_iterations: int = 12
    max_repairs: int = 4
    max_tokens: int = 250_000
    max_cost: float = 5.0


@dataclass
class ZLoopState:
    loop_id: str
    tenant_id: str
    actor_id: str
    goal: str
    acceptance_criteria: list[str]
    phase: LoopPhase = LoopPhase.DISCOVER
    iteration: int = 0
    repairs: int = 0
    tokens_used: int = 0
    cost_used: float = 0.0
    evidence: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


class StateAuthority(Protocol):
    def save_zloop_state(self, state: ZLoopState) -> None: ...


class ApprovalAuthority(Protocol):
    def authorize_zloop_mutation(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        action: str,
        target: str,
        idempotency_key: str,
    ) -> bool: ...


class WorkDispatcher(Protocol):
    def dispatch_zloop_step(
        self,
        *,
        state: ZLoopState,
        phase: LoopPhase,
        idempotency_key: str,
    ) -> Mapping[str, Any]: ...


class IndependentVerifier(Protocol):
    def verify_zloop_result(
        self,
        *,
        state: ZLoopState,
        criteria: Sequence[str],
    ) -> Mapping[str, Any]: ...


class AuditAuthority(Protocol):
    def record_zloop_event(self, event: Mapping[str, Any]) -> None: ...


def stable_idempotency_key(state: ZLoopState, phase: LoopPhase, target: str) -> str:
    payload = json.dumps(
        {
            "loop_id": state.loop_id,
            "tenant_id": state.tenant_id,
            "actor_id": state.actor_id,
            "phase": phase.value,
            "iteration": state.iteration,
            "target": target,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ZLoopCoordinator:
    """Bounded ZLoop lifecycle mapped onto existing zWorkforce authorities.

    This class intentionally owns no database, queue, credential, approval or
    provider implementation. Those remain zWorkforce authorities and are
    injected through ports above.
    """

    def __init__(
        self,
        *,
        state_authority: StateAuthority,
        approval_authority: ApprovalAuthority,
        dispatcher: WorkDispatcher,
        verifier: IndependentVerifier,
        audit: AuditAuthority,
    ) -> None:
        self.state_authority = state_authority
        self.approval_authority = approval_authority
        self.dispatcher = dispatcher
        self.verifier = verifier
        self.audit = audit

    def _persist(self, state: ZLoopState, event: str) -> None:
        self.state_authority.save_zloop_state(state)
        self.audit.record_zloop_event(
            {
                "event": event,
                "loop_id": state.loop_id,
                "tenant_id": state.tenant_id,
                "actor_id": state.actor_id,
                "phase": state.phase.value,
                "iteration": state.iteration,
            }
        )

    @staticmethod
    def _budget_exhausted(state: ZLoopState, budget: LoopBudget) -> str | None:
        if state.iteration >= budget.max_iterations:
            return "max_iterations"
        if state.repairs > budget.max_repairs:
            return "max_repairs"
        if state.tokens_used > budget.max_tokens:
            return "max_tokens"
        if state.cost_used > budget.max_cost:
            return "max_cost"
        return None

    def advance(self, state: ZLoopState, budget: LoopBudget) -> ZLoopState:
        if not state.tenant_id or not state.actor_id:
            raise ValueError("tenant_id and actor_id are mandatory")
        if not state.acceptance_criteria:
            raise ValueError("acceptance criteria are mandatory")
        if state.phase in TERMINAL:
            return state

        budget_reason = self._budget_exhausted(state, budget)
        if budget_reason:
            state.phase = LoopPhase.HANDOFF
            state.blockers.append(budget_reason)
            self._persist(state, "zloop.handoff.budget")
            return state

        current = state.phase
        key = stable_idempotency_key(state, current, state.goal)

        if current in {LoopPhase.EXECUTE, LoopPhase.REPAIR}:
            authorized = self.approval_authority.authorize_zloop_mutation(
                tenant_id=state.tenant_id,
                actor_id=state.actor_id,
                action=current.value.lower(),
                target=state.goal,
                idempotency_key=key,
            )
            if not authorized:
                state.phase = LoopPhase.HANDOFF
                state.blockers.append("mutation_not_authorized")
                self._persist(state, "zloop.handoff.authorization")
                return state

        if current == LoopPhase.VERIFY:
            result = self.verifier.verify_zloop_result(
                state=state,
                criteria=tuple(state.acceptance_criteria),
            )
            verdict = str(result.get("verdict", "INCONCLUSIVE")).upper()
            evidence = result.get("evidence", [])
            if isinstance(evidence, list):
                state.evidence.extend(str(item) for item in evidence)
            if verdict == "PASS":
                state.phase = LoopPhase.REVIEW
            elif verdict == "FAIL":
                state.phase = LoopPhase.REPAIR
            else:
                state.phase = LoopPhase.HANDOFF
                state.blockers.append("verification_inconclusive")
            state.iteration += 1
            self._persist(state, "zloop.verify")
            return state

        result = self.dispatcher.dispatch_zloop_step(
            state=state,
            phase=current,
            idempotency_key=key,
        )
        state.tokens_used += int(result.get("tokens", 0))
        state.cost_used += float(result.get("cost", 0.0))
        evidence = result.get("evidence", [])
        if isinstance(evidence, list):
            state.evidence.extend(str(item) for item in evidence)

        if current == LoopPhase.DISCOVER:
            state.phase = LoopPhase.PLAN
        elif current == LoopPhase.PLAN:
            state.phase = LoopPhase.EXECUTE
        elif current == LoopPhase.EXECUTE:
            state.phase = LoopPhase.VERIFY
        elif current == LoopPhase.REVIEW:
            blocking = bool(result.get("blocking_findings", False))
            state.phase = LoopPhase.REPAIR if blocking else LoopPhase.SHIPPED
        elif current == LoopPhase.REPAIR:
            state.repairs += 1
            state.phase = LoopPhase.VERIFY
        else:
            state.phase = LoopPhase.FAILED
            state.blockers.append("illegal_phase")

        state.iteration += 1
        self._persist(state, "zloop.advance")
        return state
