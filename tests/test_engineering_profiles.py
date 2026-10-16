"""Security-oriented contract tests for engineering profile parsing."""
import unittest

from zworkforce.engineering_profiles import (
    EngineeringProfileError,
    parse_engineering_profile,
)


class EngineeringProfileTests(unittest.TestCase):
    def test_personal_offline_defaults_are_deny_by_default(self):
        profile = parse_engineering_profile({})
        self.assertEqual(profile.mode, "local")
        self.assertEqual(profile.repository_allowlist, ())
        self.assertFalse(profile.auto_merge)
        self.assertFalse(profile.allow_production_deploy)
        self.assertTrue(profile.require_independent_review)

    def test_custom_user_accounts_do_not_depend_on_zeazdev(self):
        p = parse_engineering_profile({
            "profile": "organization",
            "execution": {"mode": "connected"},
            "github": {
                "reviewer_account": "alice-review",
                "merger_account": "bob-merge",
                "repository_allowlist": ["my-org/my-repo"],
            },
        })
        self.assertEqual(p.merger_account, "bob-merge")
        self.assertEqual(p.repository_allowlist, ("my-org/my-repo",))

    def test_denies_security_gate_disabling(self):
        for payload in (
            {"execution": {"auto_merge": True}},
            {"execution": {"allow_production_deploy": True}},
            {"github": {"require_independent_review": False}},
            {"github": {"require_required_checks": False}},
            {"github": {"reviewer_account": "alice", "merger_account": "ALICE"}},
            {"github": {"reviewer_account": "not a user"}},
            {"github": {"repository_allowlist": ["../secrets"]}},
            {"github": {"token": "should-not-be-here"}},
            {"profile": "unknown"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(EngineeringProfileError):
                    parse_engineering_profile(payload)


if __name__ == "__main__":
    unittest.main()
