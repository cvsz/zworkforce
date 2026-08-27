from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"release verification failed: {message}")


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def package_version() -> str:
    data = tomllib.loads(read("pyproject.toml"))
    return str(data["project"]["version"])


def init_version() -> str:
    text = read("zworkforce/__init__.py")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', text, re.M)
    if not match:
        fail("zworkforce.__version__ is missing")
    return match.group(1)


def require_text(relative: str, needle: str, description: str | None = None) -> None:
    text = read(relative)
    if needle not in text:
        fail(description or f"{relative} is missing required text {needle!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify zWorkforce release metadata is internally consistent")
    parser.add_argument("--expected", default="", help="expected semantic version without the v prefix")
    args = parser.parse_args()

    pyproject_version = package_version()
    module_version = init_version()
    expected = args.expected or pyproject_version

    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", expected):
        fail(f"invalid expected version {expected!r}")
    if pyproject_version != expected:
        fail(f"pyproject version {pyproject_version!r} != expected {expected!r}")
    if module_version != expected:
        fail(f"module version {module_version!r} != expected {expected!r}")

    changelog = read("CHANGELOG.md")
    if f"## {expected} " not in changelog and f"## {expected}\n" not in changelog:
        fail(f"CHANGELOG has no {expected} section")

    require_text("Makefile", f"VERSION ?= {expected}", "Makefile version is not aligned with the release candidate")
    require_text("zworkforce/static/index.html", f"v{expected}", "dashboard does not display the release candidate version")

    compose = read("compose.yaml")
    if f"zworkforce:{expected}" not in compose:
        fail(f"compose.yaml does not reference zworkforce:{expected}")

    canonical_k8s_tag = f"v{expected}"
    k8s = list((ROOT / "deploy" / "kubernetes").rglob("*.yaml"))
    image_refs = []
    for path in k8s:
        text = path.read_text(encoding="utf-8")
        image_refs.extend(re.findall(r"ghcr\.io/cvsz/zworkforce:([^\s\"']+)", text))
    stale = sorted({tag for tag in image_refs if tag != canonical_k8s_tag})
    if stale:
        fail(f"Kubernetes image tags are inconsistent; expected {canonical_k8s_tag}: {stale}")
    if not image_refs:
        fail("no Kubernetes zWorkforce image reference found")

    publish = read(".github/workflows/publish-container.yml")
    for needle in [
        f"default: v{expected}",
        f"default: {expected}",
        'python scripts/verify_release.py --expected "$RELEASE_VERSION"',
        "Refusing to overwrite existing immutable image tag",
    ]:
        if needle not in publish:
            fail(f"publish-container workflow is missing release guard {needle!r}")

    operations = read("docs/GITHUB-OPERATIONS.md")
    for needle in [
        ".github/rulesets/main.json",
        ".github/workflows/release.yml",
        ".github/workflows/publish-container.yml",
        "GHCR",
        "docs/PRODUCTION-EVIDENCE.md",
    ]:
        if needle not in operations:
            fail(f"GitHub operations runbook is missing {needle!r}")

    ruleset_path = ROOT / ".github" / "rulesets" / "main.json"
    try:
        ruleset = json.loads(ruleset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"main ruleset contract is unreadable: {exc}")
    rule_types = {rule.get("type") for rule in ruleset.get("rules", [])}
    required_rule_types = {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}
    if not required_rule_types.issubset(rule_types):
        fail(f"main ruleset contract is missing rules: {sorted(required_rule_types - rule_types)}")
    status_rule = next(rule for rule in ruleset["rules"] if rule.get("type") == "required_status_checks")
    contexts = {
        item.get("context")
        for item in status_rule.get("parameters", {}).get("required_status_checks", [])
    }
    for context in [
        "documentation-contract",
        "dependency-review",
        "build-test-package",
        "Analyze (python)",
        "Analyze (actions)",
        "CodeQL",
    ]:
        if context not in contexts:
            fail(f"main ruleset contract is missing required context {context!r}")
    for conditional in ["migration-contract", "node-workspace", "zarvis-api", "zarvis-windows-linux-restore"]:
        if conditional in contexts:
            fail(f"path-filtered ZARVIS context must not be globally required: {conditional}")

    evidence = read("docs/PRODUCTION-EVIDENCE.md")
    if f"Candidate version | `{expected}`" not in evidence:
        fail("production evidence ledger is not aligned with the candidate version")
    if "PENDING EXTERNAL EVIDENCE" not in evidence:
        fail("production evidence ledger must preserve the external-evidence boundary")

    required = [
        ROOT / ".github" / "workflows" / "ci.yml",
        ROOT / ".github" / "workflows" / "codeql.yml",
        ROOT / ".github" / "workflows" / "dependency-review.yml",
        ROOT / ".github" / "workflows" / "release.yml",
        ROOT / ".github" / "workflows" / "publish-container.yml",
        ROOT / ".github" / "workflows" / "windows-client.yml",
        ROOT / ".github" / "rulesets" / "main.json",
        ROOT / "docs" / "GITHUB-OPERATIONS.md",
        ROOT / "docs" / "PRODUCTION-EVIDENCE.md",
        ROOT / "docs" / "PRODUCTION-READINESS.md",
        ROOT / "docs" / "DISASTER-RECOVERY.md",
        ROOT / "docs" / "RELEASE.md",
        ROOT / "docs" / "SECRET-MANAGEMENT.md",
        ROOT / "scripts" / "backup-postgres.sh",
        ROOT / "scripts" / "restore-postgres.sh",
        ROOT / "scripts" / "lib" / "postgres-connection.sh",
        ROOT / "scripts" / "smoke-test.sh",
        ROOT / "scripts" / "generate_sbom.py",
        ROOT / "tests" / "test_repository_policy.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        fail(f"required release files missing: {', '.join(missing)}")

    print(f"release verification passed for zWorkforce {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
