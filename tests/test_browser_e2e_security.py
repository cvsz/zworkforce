import asyncio
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
    _safe_url_metadata,
)
from app.services.browser_effects import DurableBrowserEffectExecutor
from app.services.browser_executor import PinnedBrowserExecutor

PUBLIC_IP = "93.184.216.34"
SECOND_IP = "93.184.216.35"


class StrictTransport:
    """Fake transport that enforces the same contract as the Playwright adapter."""

    enforces_pinned_destination = True
    disables_automatic_redirects = True
    verifies_tls_server_identity = True

    def __init__(self, results=None, error=None, hang=False):
        self.calls = []
        self.results = list(results or [])
        self.error = error
        self.hang = hang

    async def request(self, *, action, connect_ip, host_header, tls_server_name, timeout_seconds):
        self.calls.append((action.url, connect_ip, host_header, tls_server_name))
        expected_ip = action.resolved_addresses[0]
        if connect_ip != expected_ip:
            raise BrowserPolicyError("transport connected to an unapproved address")
        expected_host = action.url.split("//", 1)[1].split("/", 1)[0].split(":")[0]
        if tls_server_name != expected_host:
            raise BrowserPolicyError("transport TLS identity does not match the destination host")
        if self.hang:
            await asyncio.sleep(30)
        if self.error is not None:
            raise self.error
        if self.results:
            return dict(self.results.pop(0))
        return {"ok": True, "title": "ok"}


class StatefulEffectController:
    """In-process stand-in for the zWorkforce browser-effects control plane."""

    def __init__(self):
        self.effects = {}
        self.finished = []

    async def begin(self, action, approval_task_id):
        key = action.idempotency_key
        if key in self.effects:
            return self.effects[key]
        effect_id = f"effect-{len(self.effects) + 1}"
        effect = {"id": effect_id, "status": "not_started", "result_sha256": ""}
        self.effects[key] = effect
        self.effects[effect_id] = effect
        return effect

    async def claim(self, effect_id):
        effect = self.effects[effect_id]
        if effect["status"] == "not_started":
            effect["status"] = "executing"
            return (effect, True)
        return (effect, False)

    async def finish(self, effect_id, *, status, result_sha256="", error_code=""):
        self.finished.append((effect_id, status, result_sha256, error_code))
        self.effects[effect_id]["status"] = status
        self.effects[effect_id]["result_sha256"] = result_sha256
        return self.effects[effect_id]


def approved_token():
    return "123e4567-e89b-12d3-a456-426614174000"


APPROVED_ACTION = ("https://example.com/settings", "button#save")


def approve(action, token):
    if token != approved_token():
        return False
    if action.kind != "click":
        return False
    return (_safe_url_metadata(action.url), action.selector) == APPROVED_ACTION


class BrowserE2eSecurityRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.controller = StatefulEffectController()

    def tearDown(self):
        AgentRunner.reset()

    def configure(self, transport, resolver=None, cancel_checker=None):
        executor = PinnedBrowserExecutor(
            transport,
            redirect_validator=AgentRunner._validate_url,
            timeout_seconds=5,
        )
        durable = DurableBrowserEffectExecutor(executor, self.controller, cancel_checker=cancel_checker)
        AgentRunner.configure(
            executor=durable,
            approval_authorizer=approve,
            allowed_hosts=["example.com", "next.example.com"],
            resolver=resolver or (lambda host: [PUBLIC_IP]),
            timeout_seconds=5,
        )

    async def test_e2e_approved_click_runs_through_durable_fence(self):
        self.configure(StrictTransport())
        result = await AgentRunner.run_claw_task(
            "save",
            "test",
            actions=[{
                "kind": "click",
                "url": "https://example.com/settings?session=canary",
                "selector": "button#save",
                "idempotency_key": "e2e-click-1",
            }],
            approval_token=approved_token(),
        )
        step = result["steps"][0]
        self.assertEqual(step["kind"], "click")
        self.assertEqual(step["url"], "https://example.com/settings")
        self.assertTrue(step["mutating"])
        self.assertEqual(step["evidence"]["effect_id"], "effect-1")
        self.assertEqual(len(step["evidence"]["result_sha256"]), 64)
        self.assertEqual(self.controller.finished[-1][1], "succeeded")
        rendered = json.dumps(result)
        self.assertNotIn("session=canary", rendered)
        self.assertNotIn("canary", rendered)

    async def test_e2e_dns_rebinding_cannot_escape_validated_pin(self):
        transport = StrictTransport()
        self.configure(transport, resolver=lambda host: [PUBLIC_IP])
        await AgentRunner.run_claw_task(
            "inspect",
            "test",
            actions=[{"kind": "inspect", "url": "https://example.com/page"}],
        )
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][1], PUBLIC_IP)

        self.configure(StrictTransport(), resolver=lambda host: ["127.0.0.1"])
        with self.assertRaisesRegex(BrowserPolicyError, "non-public"):
            await AgentRunner.run_claw_task(
                "inspect",
                "test",
                actions=[{"kind": "inspect", "url": "https://example.com/page"}],
            )

    async def test_e2e_approval_replay_with_different_action_is_denied(self):
        self.configure(StrictTransport())
        with self.assertRaises(BrowserApprovalRequired):
            await AgentRunner.run_claw_task(
                "save",
                "test",
                actions=[{
                    "kind": "click",
                    "url": "https://example.com/other",
                    "selector": "button#other",
                    "idempotency_key": "e2e-replay-1",
                }],
                approval_token=approved_token(),
            )
        self.assertEqual(self.controller.finished, [])

    async def test_e2e_mutation_redirect_fails_closed_without_replay(self):
        transport = StrictTransport(results=[{"redirect_url": "https://next.example.com/receipt"}])
        self.configure(transport)
        with self.assertRaisesRegex(BrowserPolicyError, "side-effect reconciliation"):
            await AgentRunner.run_claw_task(
                "save",
                "test",
                actions=[{
                    "kind": "click",
                    "url": "https://example.com/settings",
                    "selector": "button#save",
                    "idempotency_key": "e2e-mut-redirect-1",
                }],
                approval_token=approved_token(),
            )
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(self.controller.finished[-1][1], "unknown")
        self.assertEqual(self.controller.finished[-1][3], "execution_ambiguous")

    async def test_e2e_read_only_multi_hop_redirect_revalidates_and_repins(self):
        transport = StrictTransport(results=[
            {"redirect_url": "https://example.com/mid"},
            {"redirect_url": "https://next.example.com/final"},
            {"ok": True, "title": "final"},
        ])
        self.configure(transport, resolver=lambda host: { "example.com": [PUBLIC_IP], "next.example.com": [SECOND_IP]}[host])
        result = await AgentRunner.run_claw_task(
            "read",
            "test",
            actions=[{"kind": "inspect", "url": "https://example.com/start"}],
        )
        self.assertEqual(result["steps"][0]["evidence"]["redirect_count"], 2)
        self.assertEqual([call[1] for call in transport.calls], [PUBLIC_IP, PUBLIC_IP, SECOND_IP])
        self.assertEqual([call[2] for call in transport.calls], ["example.com", "example.com", "next.example.com"])
        self.assertEqual(result["steps"][0]["url"], "https://example.com/start")

    async def test_e2e_private_redirect_hop_is_rejected_before_following(self):
        transport = StrictTransport(results=[{"redirect_url": "https://next.example.com/private"}])
        self.configure(transport, resolver=lambda host: {"example.com": [PUBLIC_IP], "next.example.com": ["10.0.0.5"]}[host])
        with self.assertRaisesRegex(BrowserPolicyError, "non-public"):
            await AgentRunner.run_claw_task(
                "read",
                "test",
                actions=[{"kind": "inspect", "url": "https://example.com/start"}],
            )
        self.assertEqual(len(transport.calls), 1)

    async def test_e2e_cancellation_during_execution_marks_unknown(self):
        async def canceled(action):
            return True
        self.configure(StrictTransport(), cancel_checker=canceled)
        with self.assertRaisesRegex(BrowserAutomationUnavailable, "canceled during execution"):
            await AgentRunner.run_claw_task(
                "save",
                "test",
                actions=[{
                    "kind": "click",
                    "url": "https://example.com/settings",
                    "selector": "button#save",
                    "idempotency_key": "e2e-cancel-1",
                }],
                approval_token=approved_token(),
            )
        self.assertEqual(self.controller.finished[-1][1], "unknown")
        self.assertEqual(self.controller.finished[-1][3], "canceled_during_execution")

    async def test_e2e_execution_crash_marks_unknown_not_success(self):
        self.configure(StrictTransport(error=RuntimeError("browser crashed")))
        with self.assertRaises(RuntimeError):
            await AgentRunner.run_claw_task(
                "save",
                "test",
                actions=[{
                    "kind": "click",
                    "url": "https://example.com/settings",
                    "selector": "button#save",
                    "idempotency_key": "e2e-crash-1",
                }],
                approval_token=approved_token(),
            )
        self.assertEqual(self.controller.finished[-1][1], "unknown")

    async def test_e2e_timeout_fails_closed_before_any_success(self):
        executor = PinnedBrowserExecutor(
            StrictTransport(hang=True),
            redirect_validator=AgentRunner._validate_url,
            timeout_seconds=1,
        )
        durable = DurableBrowserEffectExecutor(executor, self.controller)
        AgentRunner.configure(
            executor=durable,
            approval_authorizer=approve,
            allowed_hosts=["example.com"],
            resolver=lambda host: [PUBLIC_IP],
            timeout_seconds=2,
        )
        with self.assertRaises(BrowserAutomationUnavailable):
            await AgentRunner.run_claw_task(
                "save",
                "test",
                actions=[{
                    "kind": "click",
                    "url": "https://example.com/settings",
                    "selector": "button#save",
                    "idempotency_key": "e2e-timeout-1",
                }],
                approval_token=approved_token(),
            )
        self.assertEqual(self.controller.effects["e2e-timeout-1"]["status"], "unknown")

    async def test_e2e_unknown_effect_never_replays(self):
        async def begin_unknown(action, task_id):
            return {"id": f"effect-{action.idempotency_key}", "status": "unknown", "result_sha256": "d" * 64}
        self.controller.begin = begin_unknown
        self.configure(StrictTransport())
        with self.assertRaisesRegex(BrowserAutomationUnavailable, "reconciliation before retry"):
            await AgentRunner.run_claw_task(
                "save",
                "test",
                actions=[{
                    "kind": "click",
                    "url": "https://example.com/settings",
                    "selector": "button#save",
                    "idempotency_key": "e2e-unknown-1",
                }],
                approval_token=approved_token(),
            )
        self.assertEqual(self.controller.finished, [])


if __name__ == "__main__":
    import asyncio

    unittest.main()