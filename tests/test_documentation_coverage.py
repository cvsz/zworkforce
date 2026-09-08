from pathlib import Path
import json
import re
import subprocess
import unittest

from zworkforce import __version__
from zworkforce.skills import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FENCED_BLOCK = re.compile(r"```.*?```", re.S)


class DocumentationCoverageTests(unittest.TestCase):
    def test_github_operations_document_is_linked_from_primary_docs(self):
        required = [
            ROOT / "README.md",
            ROOT / "docs" / "OPERATIONS.md",
            ROOT / "docs" / "RELEASE.md",
            ROOT / ".github" / "pull_request_template.md",
        ]

        for path in required:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIn(
                    "GITHUB-OPERATIONS.md",
                    path.read_text(encoding="utf-8"),
                )

    def test_prometa_master_document_is_linked_from_primary_docs(self):
        required = [
            ROOT / "README.md",
            ROOT / "docs" / "API.md",
            ROOT / "ROADMAP.md",
        ]

        for path in required:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIn(
                    "PROMETA-MASTER.md",
                    path.read_text(encoding="utf-8"),
                )

    def test_prometa_seed_catalogs_are_linked_and_valid(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        master = (ROOT / "docs" / "PROMETA-MASTER.md").read_text(encoding="utf-8")
        for name in ["prometa-agent-catalog.json", "prometa-skills.json", "prometa-agent-templates.json", "prometa-workflows.json"]:
            with self.subTest(name=name):
                self.assertIn(name, readme)
                self.assertIn(name, master)

        skills = json.loads((ROOT / "examples" / "prometa-skills.json").read_text(encoding="utf-8"))
        agents = json.loads((ROOT / "examples" / "prometa-agent-catalog.json").read_text(encoding="utf-8"))
        templates = json.loads((ROOT / "examples" / "prometa-agent-templates.json").read_text(encoding="utf-8"))
        workflows = json.loads((ROOT / "examples" / "prometa-workflows.json").read_text(encoding="utf-8"))
        skill_ids = {skill["id"] for skill in skills}
        agent_ids = {agent["id"] for agent in agents}

        for skill in skills:
            with self.subTest(skill=skill["id"]):
                validate_manifest(skill)
                skill_doc = ROOT / ".agents" / "skills" / f"zworkforce-{skill['id']}" / "SKILL.md"
                self.assertTrue(skill_doc.exists(), f"missing Codex skill for {skill['id']}")

        required_agent_fields = {
            "id",
            "name",
            "description",
            "department",
            "default_tier",
            "max_cost_credits",
            "max_iterations",
            "max_subagents",
            "required_approvals",
            "requires_approval_for_mutations",
            "allowed_tools",
            "approval_tools",
            "skill_ids",
            "system_prompt",
            "enabled",
        }
        for agent in agents:
            with self.subTest(agent=agent["id"]):
                self.assertLessEqual(required_agent_fields, set(agent))
                self.assertIn(agent["default_tier"], {"luna", "terra", "sol"})
                self.assertTrue(set(agent["skill_ids"]) <= skill_ids)
                if agent["requires_approval_for_mutations"]:
                    self.assertGreaterEqual(agent["required_approvals"], 1)
        for template in templates:
            with self.subTest(template=template["id"]):
                self.assertTrue(set(template["agent"]["skill_ids"]) <= skill_ids)
        for workflow in workflows:
            with self.subTest(workflow=workflow["id"]):
                for step in workflow["definition"]["steps"]:
                    self.assertIn(step["agent_id"], agent_ids)

        for name in ["prometa-agent-catalog.json", "prometa-skills.json", "prometa-agent-templates.json", "prometa-workflows.json"]:
            with self.subTest(package_data=name):
                self.assertEqual(
                    (ROOT / "examples" / name).read_text(encoding="utf-8"),
                    (ROOT / "zworkforce" / "prometa_data" / name).read_text(encoding="utf-8"),
                )

    def test_readme_deployment_boundary_matches_package_version(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(f"## v{__version__} highlights", readme)
        self.assertIn(f"v{__version__} provides real distributed execution", readme)

    def test_github_operations_lists_current_workflows(self):
        doc = (ROOT / "docs" / "GITHUB-OPERATIONS.md").read_text(encoding="utf-8")
        workflows = {
            path.stem
            for path in (ROOT / ".github" / "workflows").glob("*.yml")
        }

        for expected in {
            "ci",
            "zarvis",
            "windows-client",
            "codeql",
            "dependency-review",
            "release",
            "publish-container",
        }:
            with self.subTest(workflow=expected):
                self.assertIn(expected, workflows)

        for phrase in [
            "CI",
            "ZARVIS",
            "Windows client",
            "CodeQL Advanced",
            "Dependency Review",
            "release.yml",
            "publish-container.yml",
            ".github/rulesets/main.json",
            "PRODUCTION-EVIDENCE.md",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, doc)

    def test_markdown_internal_links_resolve(self):
        missing = []
        tracked = subprocess.check_output(
            ["git", "ls-files", "*.md"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).splitlines()
        for relative in tracked:
            if "/.agents/" in relative or "/.claude/" in relative or "/gitbook/" in relative:
                continue
            path = ROOT / relative
            text = path.read_text(encoding="utf-8", errors="ignore")
            text = FENCED_BLOCK.sub("", text)
            for match in MARKDOWN_LINK.finditer(text):
                target = match.group(1).split("#", 1)[0]
                if not target or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                    continue
                resolved = (path.parent / target.replace("%20", " ")).resolve()
                if not resolved.exists():
                    missing.append(f"{path.relative_to(ROOT)} -> {match.group(1)}")

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
