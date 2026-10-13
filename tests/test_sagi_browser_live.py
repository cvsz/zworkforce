"""Opt-in real Chromium smoke test.

Run only in a separately provisioned network-isolated worker:
SAGI_BROWSER_LIVE_URL=https://approved-staging.example.test/ ...
SAGI_BROWSER_LIVE_ORIGIN=https://approved-staging.example.test
SAGI_BROWSER_EGRESS_ISOLATED=1
"""
import os
import unittest

from zworkforce.sagi_browser_runtime import BrowserPolicy, run_browser_action
from zworkforce.sagi_computer_use import ComputerAction, prepare_computer_use_intent
from zworkforce.sagi_zloop_binding import PlanBinding


@unittest.skipUnless(
    os.getenv("SAGI_BROWSER_LIVE_URL") and
    os.getenv("SAGI_BROWSER_LIVE_ORIGIN") and
    os.getenv("SAGI_BROWSER_EGRESS_ISOLATED") == "1",
    "live browser test requires operator-provisioned isolated network and staging URL",
)
class BrowserLiveE2ETests(unittest.TestCase):
    def test_real_chromium_screenshot_in_isolated_sandbox(self):
        binding = PlanBinding("e2e-loop", "staging", "tester", "a" * 64, False)
        intent = prepare_computer_use_intent(
            binding=binding, session_id="e2e-session", step_id="observe",
            action=ComputerAction.OBSERVE,
            target=os.environ["SAGI_BROWSER_LIVE_URL"],
            screen_evidence_digest="b" * 64,
        )
        image = run_browser_action(
            intent=intent,
            policy=BrowserPolicy(frozenset({os.environ["SAGI_BROWSER_LIVE_ORIGIN"]})),
            url=os.environ["SAGI_BROWSER_LIVE_URL"],
            authorized=lambda x: x == intent,
        )
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
