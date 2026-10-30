#!/usr/bin/env python3
"""Read-only verification of the live GitHub default-branch ruleset."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULESET_FILE = ROOT / ".github" / "rulesets" / "main.json"
API_ROOT = "https://api.github.com"


class RulesetVerificationError(RuntimeError):
    """Raised when GitHub ruleset state cannot be read safely."""


def validate_effective_ruleset(desired: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Return policy drift findings without mutating GitHub state."""
    errors: list[str] = []

    for field in ("name", "target", "enforcement"):
        if actual.get(field) != desired.get(field):
            errors.append(
                f"{field}: expected {desired.get(field)!r}, got {actual.get(field)!r}"
            )

    expected_refs = desired.get("conditions", {}).get("ref_name", {})
    actual_refs = actual.get("conditions", {}).get("ref_name", {})
    if set(actual_refs.get("include", [])) != set(expected_refs.get("include", [])):
        errors.append("default-branch include conditions differ from desired state")
    if set(actual_refs.get("exclude", [])) != set(expected_refs.get("exclude", [])):
        errors.append("default-branch exclude conditions differ from desired state")

    bypass_actors = actual.get("bypass_actors")
    if "bypass_actors" not in actual or not isinstance(bypass_actors, list):
        errors.append(
            "UNVERIFIABLE: GitHub did not expose bypass_actors as an array; "
            "authorized ruleset-writer/admin read-back is required"
        )
    elif bypass_actors:
        errors.append("bypass_actors must be empty")
    bypass_capability = actual.get("current_user_can_bypass")
    if bypass_capability not in (None, "never"):
        errors.append(
            f"current integration bypass capability must be never, got {bypass_capability!r}"
        )

    desired_rules = desired.get("rules", [])
    actual_rules = actual.get("rules", [])
    if not isinstance(actual_rules, list):
        errors.append("rules must be a list")
        actual_rules = []

    def find_rule(rule_type: str, source: list[dict[str, Any]]) -> dict[str, Any] | None:
        matches = [rule for rule in source if rule.get("type") == rule_type]
        if len(matches) != 1:
            errors.append(f"expected exactly one {rule_type!r} rule, found {len(matches)}")
            return None
        return matches[0]

    for rule_type in ("deletion", "non_fast_forward"):
        if find_rule(rule_type, actual_rules) is None:
            continue

    desired_pr = find_rule("pull_request", desired_rules)
    actual_pr = find_rule("pull_request", actual_rules)
    if desired_pr is not None and actual_pr is not None:
        expected = desired_pr.get("parameters", {})
        observed = actual_pr.get("parameters", {})
        minimum = expected.get("required_approving_review_count", 1)
        if observed.get("required_approving_review_count", 0) < minimum:
            errors.append(
                f"required_approving_review_count must be at least {minimum}"
            )
        for field in (
            "dismiss_stale_reviews_on_push",
            "require_code_owner_review",
            "require_last_push_approval",
            "required_review_thread_resolution",
        ):
            if expected.get(field) is True and observed.get(field) is not True:
                errors.append(f"{field} must be true")
        if set(observed.get("allowed_merge_methods", [])) != set(
            expected.get("allowed_merge_methods", [])
        ):
            errors.append("allowed_merge_methods differ from desired state")

    desired_status = find_rule("required_status_checks", desired_rules)
    actual_status = find_rule("required_status_checks", actual_rules)
    if desired_status is not None and actual_status is not None:
        expected = desired_status.get("parameters", {})
        observed = actual_status.get("parameters", {})
        if observed.get("strict_required_status_checks_policy") is not True:
            errors.append("strict_required_status_checks_policy must be true")
        expected_contexts = {
            item.get("context")
            for item in expected.get("required_status_checks", [])
            if isinstance(item, dict)
        }
        actual_contexts = {
            item.get("context")
            for item in observed.get("required_status_checks", [])
            if isinstance(item, dict)
        }
        if actual_contexts != expected_contexts:
            errors.append(
                "required status-check contexts differ from desired state "
                f"(missing={sorted(expected_contexts - actual_contexts)}, "
                f"unexpected={sorted(actual_contexts - expected_contexts)})"
            )

    return errors


def _api_get(url: str, token: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "zworkforce-effective-ruleset-verifier",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RulesetVerificationError(
            f"GitHub API read failed with HTTP {exc.code}; verify token and Administration: read access"
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RulesetVerificationError(
            f"GitHub API read failed: {type(exc).__name__}"
        ) from exc


def read_effective_ruleset(repository: str, ruleset_name: str, token: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise RulesetVerificationError("repository must be in owner/name form")

    matches: list[dict[str, Any]] = []
    for page in range(1, 11):
        payload = _api_get(
            f"{API_ROOT}/repos/{repository}/rulesets?per_page=100&page={page}",
            token,
        )
        if not isinstance(payload, list):
            raise RulesetVerificationError("GitHub ruleset list response is not an array")
        matches.extend(
            item
            for item in payload
            if item.get("name") == ruleset_name and item.get("target") == "branch"
        )
        if len(payload) < 100:
            break
    if len(matches) != 1:
        raise RulesetVerificationError(
            f"expected exactly one branch ruleset named {ruleset_name!r}, found {len(matches)}"
        )

    ruleset_id = matches[0].get("id")
    if not isinstance(ruleset_id, int):
        raise RulesetVerificationError("GitHub ruleset list entry has no numeric id")
    detail = _api_get(
        f"{API_ROOT}/repos/{repository}/rulesets/{ruleset_id}",
        token,
    )
    if not isinstance(detail, dict):
        raise RulesetVerificationError("GitHub ruleset detail response is not an object")
    return detail


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only comparison of GitHub's effective default-branch ruleset."
    )
    parser.add_argument(
        "--repository",
        default=os.getenv("GITHUB_REPOSITORY", "cvsz/zworkforce"),
        help="GitHub repository in owner/name form",
    )
    parser.add_argument(
        "--ruleset-file",
        type=Path,
        default=DEFAULT_RULESET_FILE,
        help="desired-state ruleset JSON file",
    )
    args = parser.parse_args()

    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        print(
            "ERROR: provide GH_TOKEN or GITHUB_TOKEN through a secure environment "
            "with repository Administration: read permission",
            file=sys.stderr,
        )
        return 2

    try:
        desired = json.loads(args.ruleset_file.read_text(encoding="utf-8"))
        ruleset = read_effective_ruleset(args.repository, desired["name"], token)
    except (OSError, json.JSONDecodeError, KeyError, RulesetVerificationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_effective_ruleset(desired, ruleset)
    unverifiable = [error for error in errors if error.startswith("UNVERIFIABLE:")]
    if unverifiable:
        print("UNVERIFIABLE: GitHub did not expose all required effective ruleset fields")
        for error in errors:
            print(f"- {error}")
        return 2
    if errors:
        print("FAIL: effective GitHub ruleset does not match desired state")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"PASS: {args.repository} ruleset {desired['name']!r} matches "
        "the repository desired-state contract"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
