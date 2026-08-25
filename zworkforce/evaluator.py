from __future__ import annotations

import json
import re
from typing import Any


class EvaluationError(ValueError):
    pass


def validate_criteria(criteria: list[dict[str, Any]] | None) -> None:
    """Validate a success-criteria definition without evaluating content."""
    criteria = criteria or [{"type": "non_empty"}]
    if not isinstance(criteria, list):
        raise EvaluationError("success criteria must be a list")
    for raw in criteria:
        if not isinstance(raw, dict):
            raise EvaluationError("success criteria must be objects")
        kind = str(raw.get("type", "")).strip().lower()
        if kind == "contains":
            if not str(raw.get("value", "")):
                raise EvaluationError("contains criterion requires value")
        elif kind == "regex":
            pattern = str(raw.get("pattern", ""))
            if not pattern or len(pattern) > 500:
                raise EvaluationError("regex criterion requires a pattern up to 500 characters")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise EvaluationError(f"invalid regex criterion: {exc}") from exc
        elif kind == "max_chars":
            try:
                value = int(raw.get("value", 0))
            except (TypeError, ValueError) as exc:
                raise EvaluationError("max_chars criterion requires positive value") from exc
            if value <= 0:
                raise EvaluationError("max_chars criterion requires positive value")
        elif kind not in {"non_empty", "json"}:
            raise EvaluationError(f"unsupported success criterion: {kind}")


def evaluate(content: str, criteria: list[dict[str, Any]] | None) -> tuple[str, float, dict[str, Any]]:
    criteria = criteria or [{"type": "non_empty"}]
    validate_criteria(criteria)
    checks: list[dict[str, Any]] = []
    passed = 0
    for raw in criteria:
        kind = str(raw.get("type", "")).strip().lower()
        ok = False
        detail: dict[str, Any] = {"type": kind}
        if kind == "non_empty":
            ok = bool(content.strip())
        elif kind == "contains":
            value = str(raw.get("value", ""))
            if not value:
                raise EvaluationError("contains criterion requires value")
            ok = value in content
            detail["value"] = value[:200]
        elif kind == "regex":
            pattern = str(raw.get("pattern", ""))
            ok = bool(re.search(pattern, content, flags=re.MULTILINE))
            detail["pattern"] = pattern
        elif kind == "json":
            try:
                json.loads(content)
                ok = True
            except json.JSONDecodeError:
                ok = False
        elif kind == "max_chars":
            value = int(raw.get("value", 0))
            ok = len(content) <= value
            detail["value"] = value
        detail["passed"] = ok
        checks.append(detail)
        passed += int(ok)
    score = passed / len(checks) if checks else 0.0
    return ("passed" if passed == len(checks) else "failed", round(score, 6), {"checks": checks})
