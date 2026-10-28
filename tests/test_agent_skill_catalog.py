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
        (agents / "example.md").write_text(
            "---\nname: zeaz-example\ndescription: Example agent\nversion: 1.0.0\n---\n# Example\n",
            encoding="utf-8",
        )
        (skills / "SKILL.md").write_text(
            "---\nname: example-skill\ndescription: Example skill\nversion: 1.0.0\n---\n# Example skill\n",
            encoding="utf-8",
        )
        manifest = source_root / "manifest-source.json"
        manifest.write_text(
            json.dumps({
                "schema_version": "1.0.0",
                "release": {"name": "catalog", "version": "1.0.0", "status": "candidate"},
                "agents": ["example"],
                "skills": ["example-skill"],
                "policy": {
                    "default_mutation": "deny",
                    "human_approval_for_high_impact": True,
                    "independent_review": True,
                    "tenant_isolation": True,
                },
            }),
            encoding="utf-8",
        )
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



    def test_installer_rejects_non_object_manifest_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            paths = self._prepare_installer(base)
            _, _, _, manifest, _ = paths
            manifest.write_text("[]", encoding="utf-8")

            target = base / "target"
            result, error = self._run_installer(target, paths)

            self.assertEqual(result, 1)
            self.assertIn("manifest must be a JSON object", error)
            self.assertFalse(target.exists())

    def test_installer_rejects_invalid_manifest_version_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            paths = self._prepare_installer(base)
            _, _, _, manifest, _ = paths
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["release"]["version"] = "latest"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            target = base / "target"
            result, error = self._run_installer(target, paths)

            self.assertEqual(result, 1)
            self.assertIn("manifest.release.version must match 'X.Y.Z'", error)
            self.assertFalse(target.exists())

    def test_installer_refuses_blocked_release_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            paths = self._prepare_installer(base)
            _, _, _, manifest, _ = paths
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["release"]["status"] = "blocked"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            target = base / "target"
            result, error = self._run_installer(target, paths)

            self.assertEqual(result, 1)
            self.assertIn("refusing to install a blocked catalog release", error)
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


    def test_validator_reports_malformed_manifest_shapes_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            manifest.write_text(
                json.dumps({
                    "schema_version": "1.0.0",
                    "release": [],
                    "agents": [{"not": "a string"}],
                    "skills": None,
                    "policy": None,
                }),
                encoding="utf-8",
            )
            with patch.object(VALIDATOR, "MANIFEST", manifest):
                errors = VALIDATOR.validate()

        self.assertIn("manifest.release must be an object", errors)
        self.assertIn("manifest.skills must be an array", errors)
        self.assertIn("manifest.policy must be an object", errors)
        self.assertTrue(any("invalid agent identifier" in error for error in errors))


    def test_validator_rejects_non_string_release_status_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            manifest.write_text(
                json.dumps({
                    "schema_version": "1.0.0",
                    "release": {"name": "catalog", "version": "1.0.0", "status": []},
                    "agents": [],
                    "skills": [],
                    "policy": {
                        "default_mutation": "deny",
                        "human_approval_for_high_impact": True,
                        "independent_review": True,
                        "tenant_isolation": True,
                    },
                }),
                encoding="utf-8",
            )
            with patch.object(VALIDATOR, "MANIFEST", manifest):
                errors = VALIDATOR.validate()

        self.assertIn("manifest.release.status has an unsupported value", errors)



    def test_validator_enforces_release_manifest_schema_constraints(self):
        baseline = json.loads(VALIDATOR.MANIFEST.read_text(encoding="utf-8"))
        cases = [
            (
                "invalid semantic version",
                lambda manifest: manifest["release"].update(version="latest"),
                "manifest.release.version must match 'X.Y.Z'",
            ),
            (
                "unexpected top-level property",
                lambda manifest: manifest.update(unexpected=True),
                "manifest has unexpected properties",
            ),
            (
                "unexpected release property",
                lambda manifest: manifest["release"].update(unexpected=True),
                "manifest.release has unexpected properties",
            ),
            (
                "unexpected policy property",
                lambda manifest: manifest["policy"].update(unexpected=True),
                "manifest.policy has unexpected properties",
            ),
            (
                "empty agents",
                lambda manifest: manifest.update(agents=[]),
                "manifest.agents must contain at least one item",
            ),
            (
                "empty skills",
                lambda manifest: manifest.update(skills=[]),
                "manifest.skills must contain at least one item",
            ),
        ]

        for label, mutate, expected_error in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temp_dir:
                payload = json.loads(json.dumps(baseline))
                mutate(payload)
                manifest_path = Path(temp_dir) / "manifest.json"
                manifest_path.write_text(json.dumps(payload), encoding="utf-8")
                with patch.object(VALIDATOR, "MANIFEST", manifest_path):
                    errors = VALIDATOR.validate()
                self.assertTrue(
                    any(expected_error in error for error in errors),
                    f"{label}: expected {expected_error!r} in {errors!r}",
                )

if __name__ == "__main__":
    unittest.main()

    def test_validator_rejects_unexpected_properties_at_all_schema_levels(self):
        base = json.loads(VALIDATOR.MANIFEST.read_text(encoding="utf-8"))
        mutations = [
            (lambda value: value.update({"unexpected": True}), "manifest has unexpected properties"),
            (lambda value: value["release"].update({"unexpected": True}), "manifest.release has unexpected properties"),
            (lambda value: value["policy"].update({"unexpected": True}), "manifest.policy has unexpected properties"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            for mutate, expected_error in mutations:
                with self.subTest(expected_error=expected_error):
                    payload = json.loads(json.dumps(base))
                    mutate(payload)
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                    with patch.object(VALIDATOR, "MANIFEST", manifest):
                        errors = VALIDATOR.validate()
                    self.assertTrue(any(expected_error in error for error in errors), errors)

    def test_validator_rejects_empty_agent_and_skill_arrays(self):
        payload = json.loads(VALIDATOR.MANIFEST.read_text(encoding="utf-8"))
        payload["agents"] = []
        payload["skills"] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(VALIDATOR, "MANIFEST", manifest):
                errors = VALIDATOR.validate()
        self.assertIn("manifest.agents must contain at least one item", errors)
        self.assertIn("manifest.skills must contain at least one item", errors)

    def test_validator_rejects_integer_values_for_boolean_policy_fields(self):
        base = json.loads(VALIDATOR.MANIFEST.read_text(encoding="utf-8"))
        fields = (
            "human_approval_for_high_impact",
            "independent_review",
            "tenant_isolation",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            for field in fields:
                with self.subTest(field=field):
                    payload = json.loads(json.dumps(base))
                    payload["policy"][field] = 1
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                    with patch.object(VALIDATOR, "MANIFEST", manifest):
                        errors = VALIDATOR.validate()
                    self.assertIn(f"policy.{field} must equal True", errors)

