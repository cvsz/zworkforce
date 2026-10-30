from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.verify_effective_ruleset import validate_effective_ruleset


ROOT = Path(__file__).resolve().parents[1]
DESIRED = json.loads(
    (ROOT / ".github" / "rulesets" / "main.json").read_text(encoding="utf-8")
)


def effective_ruleset() -> dict:
    result = deepcopy(DESIRED)
    result["bypass_actors"] = []
    result["current_user_can_bypass"] = "never"
    return result


class EffectiveRulesetVerifierTests(unittest.TestCase):
    def test_exact_effective_state_passes(self):
        self.assertEqual([], validate_effective_ruleset(DESIRED, effective_ruleset()))

    def test_review_and_bypass_drift_fails_closed(self):
        actual = effective_ruleset()
        pr_rule = next(rule for rule in actual["rules"] if rule["type"] == "pull_request")
        pr_rule["parameters"]["required_approving_review_count"] = 0
        pr_rule["parameters"]["require_code_owner_review"] = False
        pr_rule["parameters"]["require_last_push_approval"] = False
        actual["bypass_actors"] = [
            {"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}
        ]
        actual["current_user_can_bypass"] = "always"

        errors = validate_effective_ruleset(DESIRED, actual)

        self.assertTrue(any("required_approving_review_count" in item for item in errors))
        self.assertIn("require_code_owner_review must be true", errors)
        self.assertIn("require_last_push_approval must be true", errors)
        self.assertIn("bypass_actors must be empty", errors)
        self.assertTrue(any("bypass capability" in item for item in errors))

    def test_hidden_bypass_actor_field_is_unverifiable(self):
        actual = effective_ruleset()
        del actual["bypass_actors"]

        errors = validate_effective_ruleset(DESIRED, actual)

        self.assertTrue(
            any(
                item.startswith("UNVERIFIABLE:") and "bypass_actors" in item
                for item in errors
            )
        )
        self.assertNotIn("bypass_actors must be empty", errors)

    def test_malformed_bypass_actor_field_is_unverifiable(self):
        for value in (None, {}):
            with self.subTest(value=value):
                actual = effective_ruleset()
                actual["bypass_actors"] = value

                errors = validate_effective_ruleset(DESIRED, actual)

                self.assertTrue(
                    any(
                        item.startswith("UNVERIFIABLE:") and "bypass_actors" in item
                        for item in errors
                    )
                )
                self.assertNotIn("bypass_actors must be empty", errors)

    def test_missing_or_unexpected_status_context_fails(self):
        actual = effective_ruleset()
        status_rule = next(
            rule for rule in actual["rules"] if rule["type"] == "required_status_checks"
        )
        contexts = status_rule["parameters"]["required_status_checks"]
        contexts.pop()
        contexts.append({"context": "unreviewed-extra-check"})

        errors = validate_effective_ruleset(DESIRED, actual)

        self.assertTrue(any("required status-check contexts differ" in item for item in errors))

    def test_inactive_or_wrong_branch_ruleset_fails(self):
        actual = effective_ruleset()
        actual["enforcement"] = "disabled"
        actual["conditions"]["ref_name"]["include"] = ["refs/heads/release"]

        errors = validate_effective_ruleset(DESIRED, actual)

        self.assertIn("enforcement: expected 'active', got 'disabled'", errors)
        self.assertIn("default-branch include conditions differ from desired state", errors)

    def test_missing_review_or_status_rules_fail(self):
        actual = effective_ruleset()
        actual["rules"] = [
            rule for rule in actual["rules"]
            if rule["type"] not in {"pull_request", "required_status_checks"}
        ]

        errors = validate_effective_ruleset(DESIRED, actual)

        self.assertTrue(any("pull_request" in item for item in errors))
        self.assertTrue(any("required_status_checks" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
