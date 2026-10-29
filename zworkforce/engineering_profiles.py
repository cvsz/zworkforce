"""Validate non-secret engineering profiles before any runtime registration."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_USERNAME = re.compile(r"^(?!.*--)[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_PROFILES = frozenset({"personal", "organization", "zeazdev-internal"})
_MODES = frozenset({"local", "connected"})


class EngineeringProfileError(ValueError):
    """Invalid or unsafe engineering profile."""


@dataclass(frozen=True)
class EngineeringProfile:
    profile: str
    mode: str
    repository_allowlist: tuple[str, ...]
    reviewer_account: str | None
    merger_account: str | None
    require_independent_review: bool
    require_required_checks: bool
    auto_merge: bool
    allow_production_deploy: bool


def _keys(obj: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if any(not isinstance(key, str) for key in obj):
        raise EngineeringProfileError(f"{field} keys must be strings")
    unexpected = set(obj) - allowed
    if unexpected:
        raise EngineeringProfileError(f"unknown {field} keys: {', '.join(sorted(map(str, unexpected)))}")


def _account(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _USERNAME.fullmatch(value):
        raise EngineeringProfileError(f"invalid {field}")
    return value


def _bool(value: Any, field: str, expected: bool) -> bool:
    if not isinstance(value, bool) or value is not expected:
        raise EngineeringProfileError(f"{field} must be {str(expected).lower()}")
    return value


def parse_engineering_profile(raw: Mapping[str, Any]) -> EngineeringProfile:
    """Parse a deny-by-default profile; this does not grant execution authority."""
    if not isinstance(raw, Mapping):
        raise EngineeringProfileError("profile must be an object")
    _keys(raw, {"profile", "execution", "github"}, "profile")
    profile = raw.get("profile", "personal")
    if not isinstance(profile, str) or profile not in _PROFILES:
        raise EngineeringProfileError("unsupported profile")
    execution = raw.get("execution", {})
    github = raw.get("github", {})
    if not isinstance(execution, Mapping) or not isinstance(github, Mapping):
        raise EngineeringProfileError("execution and github must be objects")
    _keys(execution, {"mode", "auto_merge", "allow_production_deploy"}, "execution")
    _keys(github, {"provider", "reviewer_account", "merger_account", "repository_allowlist",
                   "require_independent_review", "require_required_checks"}, "github")
    mode = execution.get("mode", "local")
    if not isinstance(mode, str) or mode not in _MODES:
        raise EngineeringProfileError("unsupported execution mode")
    if not isinstance(github.get("provider", "github"), str) or github.get("provider", "github") != "github":
        raise EngineeringProfileError("unsupported git provider")
    reviewer = _account(github.get("reviewer_account"), "reviewer_account")
    merger = _account(github.get("merger_account"), "merger_account")
    if reviewer and merger and reviewer.casefold() == merger.casefold():
        raise EngineeringProfileError("reviewer and merger identities must differ")
    _bool(github.get("require_independent_review", True), "require_independent_review", True)
    _bool(github.get("require_required_checks", True), "require_required_checks", True)
    auto_merge = _bool(execution.get("auto_merge", False), "auto_merge", False)
    deploy = _bool(execution.get("allow_production_deploy", False), "allow_production_deploy", False)
    repositories = github.get("repository_allowlist", [])
    if not isinstance(repositories, list) or len(repositories) > 100:
        raise EngineeringProfileError("repository_allowlist must be a list with at most 100 entries")
    if any(not isinstance(repo, str) or not _REPOSITORY.fullmatch(repo)
           or ".." in repo or repo.startswith("-") for repo in repositories):
        raise EngineeringProfileError("invalid repository allowlist entry")
    normalized = tuple(sorted(set(repositories)))
    return EngineeringProfile(profile, mode, normalized, reviewer, merger, True, True, auto_merge, deploy)
