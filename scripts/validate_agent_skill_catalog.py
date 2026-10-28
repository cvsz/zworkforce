#!/usr/bin/env python3
"""Validate the declarative agent/skill catalog using only the standard library."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "agent-skill-release-manifest.json"
AGENT_DIR = ROOT / ".agents" / "agents"
SKILL_DIR = ROOT / ".agents" / "skills"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter opener")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing YAML frontmatter closer") from exc
    result: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def validate() -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest unreadable or invalid JSON: {exc}"]

    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]

    for key in ("schema_version", "release", "agents", "skills", "policy"):
        if key not in manifest:
            errors.append(f"manifest missing required key: {key}")
    if manifest.get("schema_version") != "1.0.0":
        errors.append("manifest.schema_version must equal '1.0.0'")

    release = manifest.get("release")
    if not isinstance(release, dict):
        errors.append("manifest.release must be an object")
    else:
        for key in ("name", "version", "status"):
            if not isinstance(release.get(key), str) or not release[key].strip():
                errors.append(f"manifest.release.{key} must be a non-empty string")
        if release.get("status") not in {"candidate", "verified", "blocked", "released"}:
            errors.append("manifest.release.status has an unsupported value")

    agents_value = manifest.get("agents", [])
    if not isinstance(agents_value, list):
        errors.append("manifest.agents must be an array")
        agents: list[object] = []
    else:
        agents = agents_value
    seen_agents: set[str] = set()
    for name in agents:
        if isinstance(name, str):
            if name in seen_agents:
                errors.append(f"duplicate agent identifier: {name}")
            seen_agents.add(name)

    skills_value = manifest.get("skills", [])
    if not isinstance(skills_value, list):
        errors.append("manifest.skills must be an array")
        skills: list[object] = []
    else:
        skills = skills_value
    seen_skills: set[str] = set()
    for name in skills:
        if isinstance(name, str):
            if name in seen_skills:
                errors.append(f"duplicate skill identifier: {name}")
            seen_skills.add(name)

    for name in agents:
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"invalid agent identifier: {name!r}")
            continue
        path = AGENT_DIR / f"{name}.md"
        if not path.is_file():
            errors.append(f"agent file missing: {path.relative_to(ROOT)}")
            continue
        try:
            meta = frontmatter(path.read_text(encoding="utf-8"))
            if meta.get("name") != f"zeaz-{name}":
                errors.append(f"{path.relative_to(ROOT)} has unexpected frontmatter name")
            if not meta.get("description") or not meta.get("version"):
                errors.append(f"{path.relative_to(ROOT)} missing description/version")
        except (OSError, ValueError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    for name in skills:
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"invalid skill identifier: {name!r}")
            continue
        path = SKILL_DIR / name / "SKILL.md"
        if not path.is_file():
            errors.append(f"skill file missing: {path.relative_to(ROOT)}")
            continue
        try:
            meta = frontmatter(path.read_text(encoding="utf-8"))
            if meta.get("name") != name:
                errors.append(f"{path.relative_to(ROOT)} has unexpected frontmatter name")
            if not meta.get("description") or not meta.get("version"):
                errors.append(f"{path.relative_to(ROOT)} missing description/version")
        except (OSError, ValueError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    policy_value = manifest.get("policy", {})
    if not isinstance(policy_value, dict):
        errors.append("manifest.policy must be an object")
        policy: dict[str, object] = {}
    else:
        policy = policy_value
    for key, expected in {
        "default_mutation": "deny",
        "human_approval_for_high_impact": True,
        "independent_review": True,
        "tenant_isolation": True,
    }.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} must equal {expected!r}")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("Agent/skill catalog validation FAILED:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        raise SystemExit(1)
    print("Agent/skill catalog validation PASSED")
