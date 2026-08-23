from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.sarif_triage import SarifTriager, TriageFinding
from zworkforce.secret_canary import SecretCanaryRegistry, CanaryLeakError


class SarifTriageTests(unittest.TestCase):
    def setUp(self):
        self.triager = SarifTriager()

    def test_sarif_parsing_and_cvss_scoring(self):
        mock_sarif = {
            "runs": [{
                "tool": {
                    "driver": {
                        "rules": [
                            {"id": "py/sql-injection", "properties": {"security-severity": "9.3"}},
                            {"id": "py/unused-import", "properties": {"security-severity": "2.1"}},
                        ]
                    }
                },
                "results": [
                    {"ruleId": "py/sql-injection", "message": {"text": "SQL injection detected"}},
                    {"ruleId": "py/unused-import", "message": {"text": "Unused import sys"}},
                ]
            }]
        }
        findings = self.triager.parse_sarif(mock_sarif)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, "CRITICAL")
        self.assertEqual(findings[1].severity, "LOW")

        report = self.triager.evaluate(findings)
        self.assertFalse(report["pass"])
        self.assertEqual(report["summary"]["CRITICAL"], 1)
        self.assertEqual(report["summary"]["LOW"], 1)


class SecretCanaryTests(unittest.TestCase):
    def setUp(self):
        self.registry = SecretCanaryRegistry()

    def test_canary_injection_and_detection(self):
        token = self.registry.inject_canary("openai_key")
        self.assertTrue(token.startswith("zwf-canary-"))
        self.assertEqual(self.registry.get_canary("openai_key"), token)

        safe_log = "All tasks executed cleanly without errors."
        self.assertEqual(self.registry.scan_for_leaks(safe_log), [])

        leaked_log = f"Debug print: Authorization: Bearer {token}"
        with self.assertRaises(CanaryLeakError) as ctx:
            self.registry.scan_for_leaks(leaked_log, halt_on_leak=True)
        self.assertIn("openai_key", str(ctx.exception))

    def test_canary_redaction(self):
        token = self.registry.inject_canary("anthropic_key")
        raw = f"Header: {token}"
        redacted = self.registry.redact_canaries(raw)
        self.assertNotIn(token, redacted)
        self.assertIn("[CANARY_REDACTED]", redacted)


if __name__ == "__main__":
    unittest.main()
