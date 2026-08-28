#!/usr/bin/env python3
"""Validate that dependency locks are complete and enforced."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCKS = ("requirements.lock", "requirements-dev.lock", "requirements-build.lock")
REQUIREMENT = re.compile(r"(?m)^([A-Za-z0-9_.-]+)==([^\s\\]+)\s*\\")
SHA256 = re.compile(r"--hash=sha256:[0-9a-f]{64}")


def validate_lock(name: str) -> list[str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    matches = list(REQUIREMENT.finditer(text))
    errors: list[str] = []
    if not matches:
        return [f"{name}: contains no exact requirements"]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if not SHA256.search(text, match.end(), end):
            errors.append(f"{name}: {match.group(1)}=={match.group(2)} has no SHA-256 hash")
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "--hash")) and not line[0].isspace():
            if not REQUIREMENT.match(line):
                errors.append(f"{name}:{line_number}: requirement is not exactly pinned")
    return errors


def main() -> int:
    errors = [error for name in LOCKS for error in validate_lock(name)]
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    required_fragments = (
        "--require-hashes -r requirements-build.lock",
        "--require-hashes --wheel-dir /wheels -r requirements.lock",
        "--require-hashes -r /tmp/requirements.lock",
        "--no-build-isolation --no-deps",
        "--no-deps zeaz-provider==",
    )
    errors.extend(
        f"Dockerfile: missing enforced lock contract: {fragment}"
        for fragment in required_fragments
        if fragment not in dockerfile
    )
    if errors:
        print("\n".join(errors))
        return 1
    print(f"validated {len(LOCKS)} hashed dependency locks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
