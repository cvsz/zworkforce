"""Active regression tests for the agent/skill catalog validation contract."""
from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_agent_skill_catalog.py"
SPEC = importlib.util.spec_from_file_location("validate_agent_skill_catalog", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class CatalogSchemaRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(VALIDATOR.MANIFEST.read_text(encoding="utf-8"))

    def validate_payload(self, payload: dict) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(VALIDATOR, "MANIFEST", manifest_path):
                return VALIDATOR.validate()

    def test_semver_accepts_stable_prerelease_and_build_metadata(self):
        for version in ("2.10.3", "1.0.0-alpha.1", "1.0.0+build.5", "1.0.0-rc.1+build.7"):
            with self.subTest(version=version):
                payload = json.loads(json.dumps(self.baseline))
                payload["release"]["version"] = version
                errors = self.validate_payload(payload)
                self.assertFalse(any("release.version" in error for error in errors), errors)

    def test_semver_rejects_malformed_versions_and_numeric_leading_zeroes(self):
        invalid_versions = (
            "latest", "1.2", "1.2.3.4", "v1.2.3", "1..3",
            "01.2.3", "1.02.3", "1.2.03", "1.2.3-01", "1.2.3-", "1.2.3+",
        )
        for version in invalid_versions:
            with self.subTest(version=version):
                payload = json.loads(json.dumps(self.baseline))
                payload["release"]["version"] = version
                errors = self.validate_payload(payload)
                self.assertIn("manifest.release.version must be a valid SemVer 2.0.0 string", errors)

    def test_unknown_top_level_property_is_rejected(self):
        payload = json.loads(json.dumps(self.baseline))
        payload["unexpected"] = True
        self.assertTrue(any("manifest has unexpected properties" in e for e in self.validate_payload(payload)))

    def test_unknown_release_property_is_rejected(self):
        payload = json.loads(json.dumps(self.baseline))
        payload["release"]["unexpected"] = True
        self.assertTrue(any("manifest.release has unexpected properties" in e for e in self.validate_payload(payload)))

    def test_unknown_policy_property_is_rejected(self):
        payload = json.loads(json.dumps(self.baseline))
        payload["policy"]["unexpected"] = True
        self.assertTrue(any("manifest.policy has unexpected properties" in e for e in self.validate_payload(payload)))

    def test_empty_agents_array_is_rejected(self):
        payload = json.loads(json.dumps(self.baseline))
        payload["agents"] = []
        self.assertIn("manifest.agents must contain at least one item", self.validate_payload(payload))

    def test_empty_skills_array_is_rejected(self):
        payload = json.loads(json.dumps(self.baseline))
        payload["skills"] = []
        self.assertIn("manifest.skills must contain at least one item", self.validate_payload(payload))

    def test_policy_boolean_fields_reject_integer_one(self):
        for field in ("human_approval_for_high_impact", "independent_review", "tenant_isolation"):
            with self.subTest(field=field):
                payload = json.loads(json.dumps(self.baseline))
                payload["policy"][field] = 1
                self.assertIn(f"policy.{field} must equal True", self.validate_payload(payload))

    def test_policy_boolean_fields_reject_string_true(self):
        for field in ("human_approval_for_high_impact", "independent_review", "tenant_isolation"):
            with self.subTest(field=field):
                payload = json.loads(json.dumps(self.baseline))
                payload["policy"][field] = "true"
                self.assertIn(f"policy.{field} must equal True", self.validate_payload(payload))

    def test_default_mutation_rejects_wrong_type_and_value(self):
        for value in (True, 1, "allow", None):
            with self.subTest(value=value):
                payload = json.loads(json.dumps(self.baseline))
                payload["policy"]["default_mutation"] = value
                self.assertIn("policy.default_mutation must equal 'deny'", self.validate_payload(payload))

    def test_schema_pattern_rejects_trailing_line_terminator(self):
        schema_path = ROOT / "schemas" / "agent-skill-release-manifest.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        pattern = schema["properties"]["release"]["properties"]["version"]["pattern"]

        self.assertIsNone(re.search(pattern, "1.2.3\\n"))
        self.assertIsNotNone(re.search(pattern, "1.2.3"))


if __name__ == "__main__":
    unittest.main()
