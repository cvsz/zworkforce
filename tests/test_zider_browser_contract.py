import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

ZIDER_SERVER = Path(__file__).resolve().parent.parent / "packages" / "zider" / "server"
ROOT = Path(__file__).resolve().parent.parent
if str(ZIDER_SERVER) not in sys.path:
    sys.path = [p for p in sys.path if p != str(ROOT)]
    sys.path.insert(0, str(ZIDER_SERVER))

from app.services.agent_runner import (
    AgentRunner,
    BrowserApprovalRequired,
    BrowserAutomationUnavailable,
    BrowserPolicyError,
)


class FakeExecutor:
    enforces_resolved_addresses = True

    def __init__(self):
        self.actions = []

    async def execute(self, action):
        self.actions.append(action)
        return {"ok": True}


class ZiderBrowserContractRequiredCiTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        AgentRunner.reset()

    async def test_production_default_fails_closed_without_executor(self):
        AgentRunner.configure(allowed_hosts=["example.com"], resolver=lambda host: ["93.184.216.34"])
        with self.assertRaises(BrowserAutomationUnavailable):
            await AgentRunner.run_claw_task(
                "inspect",
                "test",
                actions=[{"kind": "inspect", "url": "https://example.com/"}],
            )

    async def test_private_destination_and_unapproved_mutation_are_denied(self):
        executor = FakeExecutor()
        AgentRunner.configure(
            executor=executor,
            allowed_hosts=["example.com"],
            resolver=lambda host: ["127.0.0.1"],
        )
        with self.assertRaises(BrowserPolicyError):
            await AgentRunner.run_claw_task(
                "inspect",
                "test",
                actions=[{"kind": "inspect", "url": "https://example.com/"}],
            )

        AgentRunner.configure(
            executor=executor,
            allowed_hosts=["example.com"],
            resolver=lambda host: ["93.184.216.34"],
        )
        with self.assertRaises(BrowserApprovalRequired):
            await AgentRunner.run_claw_task(
                "save",
                "test",
                actions=[{
                    "kind": "click",
                    "url": "https://example.com/settings?token=secret",
                    "selector": "button#save",
                    "idempotency_key": "save-1",
                }],
            )
        self.assertEqual(executor.actions, [])

    async def test_approved_action_runs_and_redacts_url_query_metadata(self):
        executor = FakeExecutor()
        AgentRunner.configure(
            executor=executor,
            approval_authorizer=lambda action, token: token == "123e4567-e89b-12d3-a456-426614174000",
            allowed_hosts=["example.com"],
            resolver=lambda host: ["93.184.216.34"],
        )
        result = await AgentRunner.run_claw_task(
            "save",
            "test",
            actions=[{
                "kind": "submit",
                "url": "https://example.com/form?token=secret#private",
                "selector": "form#settings",
                "idempotency_key": "submit-1",
            }],
            approval_token="123e4567-e89b-12d3-a456-426614174000",
        )
        self.assertEqual(result["steps"][0]["url"], "https://example.com/form")
        self.assertTrue(result["steps"][0]["mutating"])
        self.assertEqual(len(executor.actions), 1)

    async def test_step_evidence_envelope_is_whitelisted_and_redacts_secrets(self):
        executor = FakeExecutor()
        AgentRunner.configure(
            executor=executor,
            approval_authorizer=lambda action, token: token == "123e4567-e89b-12d3-a456-426614174000",
            allowed_hosts=["example.com"],
            resolver=lambda host: ["93.184.216.34"],
        )
        result = await AgentRunner.run_claw_task(
            "save",
            "test",
            actions=[{
                "kind": "submit",
                "url": "https://example.com/form?session=canary-password-xyz&token=canary-bearer-abc",
                "selector": "form#settings",
                "idempotency_key": "submit-1",
            }],
            approval_token="123e4567-e89b-12d3-a456-426614174000",
        )
        evidence = result["steps"][0]["evidence"]
        self.assertEqual(evidence["idempotency_key"], "submit-1")
        self.assertRegex(evidence["approval_task_id"], r"^[0-9a-fA-F-]{36}$")
        self.assertIn("started_at", evidence)
        self.assertIn("finished_at", evidence)
        self.assertEqual(evidence["effect_id"], "")
        self.assertEqual(evidence["redirect_count"], 0)
        self.assertIn("browser_version", evidence)
        self.assertNotIn("before", evidence)
        self.assertNotIn("after", evidence)

        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("canary-password-xyz", rendered)
        self.assertNotIn("canary-bearer-abc", rendered)
        self.assertNotIn("?session=", rendered)
        self.assertNotIn("?token=", rendered)

    async def test_mutation_evidence_carries_effect_reference_and_digest(self):
        class EvidenceExecutor(FakeExecutor):
            async def execute(self, action):
                self.actions.append(action)
                return {
                    "ok": True,
                    "effect_id": "123e4567-e89b-12d3-a456-426614174099",
                    "result_sha256": "d" * 64,
                    "browser_version": "chromium-138.0.0.0",
                    "redirect_count": 1,
                }

        executor = EvidenceExecutor()
        AgentRunner.configure(
            executor=executor,
            approval_authorizer=lambda action, token: token == "123e4567-e89b-12d3-a456-426614174000",
            allowed_hosts=["example.com"],
            resolver=lambda host: ["93.184.216.34"],
        )
        result = await AgentRunner.run_claw_task(
            "save",
            "test",
            actions=[{
                "kind": "click",
                "url": "https://example.com/settings",
                "selector": "button#save",
                "idempotency_key": "click-evidence-1",
            }],
            approval_token="123e4567-e89b-12d3-a456-426614174000",
        )
        evidence = result["steps"][0]["evidence"]
        self.assertEqual(evidence["effect_id"], "123e4567-e89b-12d3-a456-426614174099")
        self.assertEqual(evidence["result_sha256"], "d" * 64)
        self.assertEqual(evidence["redirect_count"], 1)
        self.assertEqual(evidence["browser_version"], "chromium-138.0.0.0")
        for stamp in (evidence["started_at"], evidence["finished_at"]):
            datetime.fromisoformat(stamp)


if __name__ == "__main__":
    unittest.main()
