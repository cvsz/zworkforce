"""Contract tests for the declarative agent/skill catalog."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SCRIPT = ROOT / "scripts" / "validate_agent_skill_catalog.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_agent_skill_catalog", VALIDATOR_SCRIPT)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)

INSTALLER_SCRIPT = ROOT / "scripts" / "install_agent_skill_catalog.py"
INSTALLER_SPEC = importlib.util.spec_from_file_location("install_agent_skill_catalog", INSTALLER_SCRIPT)
assert INSTALLER_SPEC and INSTALLER_SPEC.loader
INSTALLER = importlib.util.module_from_spec(INSTALLER_SPEC)
INSTALLER_SPEC.loader.exec_module(INSTALLER)


class AgentSkillCatalogTests(unittest.TestCase):
    def test_manifest_and_referenced_files_are_valid(self):
        self.assertEqual(VALIDATOR.validate(), [])

    def test_frontmatter_requires_delimiters(self):
        with self.assertRaises(ValueError):
            VALIDATOR.frontmatter("name: invalid\n")

    def test_frontmatter_parses_metadata(self):
        parsed = VALIDATOR.frontmatter("---\nname: example\ndescription: A test\n---\n")
        self.assertEqual(parsed["name"], "example")
        self.assertEqual(parsed["description"], "A test")

    def _prepare_installer(self, base: Path):
        source_root = base / "source"
        agents = source_root / ".agents" / "agents"
        skills = source_root / ".agents" / "skills" / "example-skill"
        schemas = source_root / "schemas"
        agents.mkdir(parents=True)
        skills.mkdir(parents=True)
        schemas.mkdir(parents=True)
        (agents / "example.md").write_text("# Example\n", encoding="utf-8")
        (skills / "SKILL.md").write_text("# Example skill\n", encoding="utf-8")
        manifest = source_root / "manifest-source.json"
        manifest.write_text(json.dumps({"agents": ["example"], "skills": ["example-skill"]}), encoding="utf-8")
        schema = schemas / "manifest.schema.json"
        schema.write_text("{}", encoding="utf-8")
        return source_root, agents, source_root / ".agents" / "skills", manifest, schema

    def _run_installer(self, target: Path, paths):
        source_root, agents, skills, manifest, schema = paths
        stderr = io.StringIO()
        with (
            patch.multiple(
                INSTALLER,
                ROOT=source_root,
                MANIFEST=manifest,
                AGENTS=agents,
                SKILLS=skills,
                SCHEMA=schema,
            ),
            patch.object(sys, "argv", ["install_agent_skill_catalog.py", "--target", str(target), "--apply"]),
            contextlib.redirect_stderr(stderr),
        ):
            result = INSTALLER.main()
        return result, stderr.getvalue()

    def test_installer_rejects_symlinked_destination_directory_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            target = base / "target"
            outside = base / "outside"
            target.mkdir()
            outside.mkdir()
            paths = self._prepare_installer(base)
            try:
                (target / "agents").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")

            result, error = self._run_installer(target, paths)

            self.assertEqual(result, 1)
            self.assertIn("symlink destination directory", error)
            self.assertFalse((outside / "example.md").exists())
            self.assertFalse((target / "manifest.json").exists())

    def test_installer_rejects_symlinked_target_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            outside = base / "outside"
            outside.mkdir()
            target = base / "target-link"
            paths = self._prepare_installer(base)
            try:
                target.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")

            result, error = self._run_installer(target, paths)

            self.assertEqual(result, 1)
            self.assertIn("target directory must not be a symlink", error)
            self.assertEqual(list(outside.iterdir()), [])

    def test_installer_rejects_symlinked_source_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            outside = base / "outside"
            outside.mkdir()
            (outside / "example.md").write_text("not trusted source", encoding="utf-8")
            paths = self._prepare_installer(base)
            _, agents, _, _, _ = paths
            (agents / "example.md").unlink()
            agents.rmdir()
            try:
                agents.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks are unavailable: {exc}")

            target = base / "target"
            result, error = self._run_installer(target, paths)

            self.assertEqual(result, 1)
            self.assertIn("symlink source path", error)
            self.assertFalse(target.exists())

    def test_installer_rejects_invalid_manifest_identifiers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            paths = self._prepare_installer(base)
            _, _, _, manifest, _ = paths
            manifest.write_text(json.dumps({"agents": ["../escape"], "skills": ["example-skill"]}), encoding="utf-8")

            result, error = self._run_installer(base / "target", paths)

            self.assertEqual(result, 1)
            self.assertIn("invalid agent identifier", error)
            self.assertFalse((base / "escape.md").exists())


if __name__ == "__main__":
    unittest.main()
