import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "center-control-plane.schema.json"
EXAMPLE_PATH = ROOT / "examples" / "center-control-plane.example.json"


class CenterControlPlaneContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())

    def test_schema_is_valid_and_example_conforms(self):
        Draft202012Validator.check_schema(self.schema)
        self.validator.validate(self.example)

    def test_hostname_registry_is_keyed_by_normalized_hostname(self):
        hostnames = self.schema["properties"]["hostnames"]
        self.assertEqual("object", hostnames["type"])
        self.assertIn("propertyNames", hostnames)
        self.assertEqual(
            {"$ref": "#/$defs/hostname"},
            hostnames["additionalProperties"],
        )
        self.assertFalse(self.validator.is_valid({**self.example, "hostnames": []}))

        hostname_pattern = hostnames["propertyNames"]["pattern"]
        self.assertRegex("zwf.zeaz.dev", hostname_pattern)
        self.assertRegex("*.zeaz.dev", hostname_pattern)
        self.assertNotRegex("ZWF.zeaz.dev", hostname_pattern)

    def test_hostname_verified_states_require_structured_evidence(self):
        hostname = self.example["hostnames"]["zwf.zeaz.dev"]
        self.assertIn("sourcePath", self.schema["$defs"]["hostname"]["required"])
        self.assertIn("sourceResourceAddress", self.schema["$defs"]["hostname"]["required"])
        self.assertEqual(
            "infrastructure/terraform/cloudflare/zworkforce.tf",
            hostname["sourcePath"],
        )
        self.assertEqual("cloudflare_dns_record.zwf", hostname["sourceResourceAddress"])
        self.assertFalse(self.validator.is_valid({
            **self.example,
            "hostnames": {"zwf.zeaz.dev": {key: value for key, value in hostname.items() if key != "effectiveState"}},
        }))

        verified = {**hostname, "effectiveState": "VERIFIED"}
        self.assertFalse(self.validator.is_valid({**self.example, "hostnames": {"zwf.zeaz.dev": verified}}))

        desired_verified = {**hostname, "desiredState": "VERIFIED"}
        self.assertFalse(self.validator.is_valid({**self.example, "hostnames": {"zwf.zeaz.dev": desired_verified}}))

        verified["evidence"] = {
            "subjectRevision": "a" * 40,
            "environment": "production",
            "observedAt": "2026-09-29T17:00:00Z",
            "commandOrRun": "terraform show -json plan.out",
            "result": "DNS target matches the approved plan",
            "artifactReference": "https://ci.example/runs/123/artifacts/456",
        }
        self.assertTrue(self.validator.is_valid({**self.example, "hostnames": {"zwf.zeaz.dev": verified}}))

    def test_readiness_is_tracked_per_gate_and_verified_requires_evidence(self):
        repository_schema = self.schema["$defs"]["repository"]
        self.assertIn("readinessGates", repository_schema["required"])
        self.assertNotIn("readiness", repository_schema["properties"])
        self.assertIn("readinessGates", repository_schema["properties"])

        template = self.example["repositories"][1]
        self.assertEqual("UNVERIFIED", template["readinessGates"]["foundation-review"]["status"])
        verified = {**template, "readinessGates": {"foundation-review": {"status": "VERIFIED"}}}
        self.assertFalse(self.validator.is_valid({**self.example, "repositories": [self.example["repositories"][0], verified]}))

    def test_browser_control_panel_does_not_accept_or_claim_to_store_api_keys(self):
        page = (ROOT / "apps" / "agent-control-panel" / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
        self.assertNotIn("apiKey", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("rotation pool", page)
        self.assertNotIn("useState", page)
        self.assertIn("Live GitHub and Cloudflare inventory is not connected yet.", page)


if __name__ == "__main__":
    unittest.main()
