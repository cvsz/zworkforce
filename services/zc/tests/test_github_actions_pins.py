"""Supply-chain checks for third-party GitHub Actions."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
USES_PATTERN = re.compile(r"^\s*-\s+uses:\s+([^@\s]+)@([^\s#]+)", re.MULTILINE)
COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def test_external_actions_are_pinned_to_full_commit_shas() -> None:
    unpinned: list[str] = []
    discovered = 0

    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        contents = workflow.read_text(encoding="utf-8")
        for action, ref in USES_PATTERN.findall(contents):
            if action.startswith("./"):
                continue
            discovered += 1
            if not COMMIT_SHA_PATTERN.fullmatch(ref):
                unpinned.append(f"{workflow.relative_to(ROOT)}: {action}@{ref}")

    assert discovered > 0
    assert not unpinned, "unpinned external actions:\n" + "\n".join(unpinned)
