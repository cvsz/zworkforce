import unittest

from zworkforce.capabilities import (
    CapabilityError,
    assert_safe_capability_upgrade,
    capability_fingerprint,
    validate_capability_manifest,
)
from zworkforce.skill_registry import RemoteSkillRegistry, SkillRegistryError
from zworkforce.skills import sign_manifest, validate_manifest, verify_manifest


SIGNING_KEY = "test-enterprise-capability-signing-key-with-enough-entropy"


def enterprise_skill(
    *,
    version: str = "1.0.0",
    tools: list[str] | None = None,
    mutability: str = "read_only",
    risk: str = "R1",
    approval: bool = False,
    minimum_approvals: int = 0,
    network_mode: str = "deny",
    hosts: list[str] | None = None,
    timeout_seconds: int = 300,
    visibility: str = "organization",
    evaluation_suite: str | None = "enterprise-review-v1",
    minimum_score: float = 0.9,
) -> dict:
    tools = list(tools or ["workspace_read"])
    manifest = {
        "apiVersion": "zworkforce.ai/v1",
        "kind": "Skill",
        "id": "enterprise-review",
        "version": version,
        "name": "Enterprise Review",
        "description": "Review repository evidence within a bounded capability envelope.",
        "metadata": {
            "owner": "platform-security",
            "visibility": visibility,
        },
        "allowed_tools": tools,
        "permissions": {
            "tools": list(reversed(tools)),
            "scopes": ["workspace:read"],
            "secrets": [],
        },
        "mutability": mutability,
        "approval": {
            "required": approval,
            "minimum_approvals": minimum_approvals,
        },
        "security": {"risk": risk},
        "network": {
            "mode": network_mode,
            "allowed_hosts": list(hosts or []),
        },
        "resources": {
            "timeout_seconds": timeout_seconds,
            "memory_mb": 512,
            "cpu_millis": 500,
        },
        "provenance": {
            "source": "git:cvsz/zworkforce@0123456",
            "digest": "sha256:" + "a" * 64,
        },
        "system_prompt_append": "Review evidence and do not exceed granted authority.",
    }
    if evaluation_suite is not None:
        manifest["evaluation"] = {
            "suite": evaluation_suite,
            "minimum_score": minimum_score,
        }
    return manifest


class _FakeDB:
    def __init__(self):
        self.skills = {}
        self.events = []

    def get_skill(self, tenant_id, skill_id):
        value = self.skills.get((tenant_id, skill_id))
        return dict(value) if value else None

    def upsert_skill(self, tenant_id, manifest, signature, actor, enabled=True):
        record = {
            "tenant_id": tenant_id,
            "id": manifest["id"],
            "version": manifest["version"],
            "manifest": dict(manifest),
            "signature": signature,
            "enabled": enabled,
            "actor": actor,
        }
        self.skills[(tenant_id, manifest["id"])] = record
        return dict(record)

    def audit(self, tenant_id, actor, action, target_type, target_id, details):
        self.events.append((tenant_id, actor, action, target_type, target_id, details))


class CapabilityManifestTests(unittest.TestCase):
    def test_legacy_skill_manifest_remains_compatible(self):
        manifest = {
            "id": "repo-review",
            "version": "1.0.0",
            "allowed_tools": ["workspace_read"],
            "system_prompt_append": "Review carefully.",
        }
        validate_manifest(manifest)
        signature = sign_manifest(manifest, SIGNING_KEY)
        self.assertTrue(verify_manifest(manifest, signature, SIGNING_KEY, True))

    def test_enterprise_skill_validates_and_signs(self):
        manifest = enterprise_skill()
        validate_manifest(manifest)
        validate_capability_manifest(manifest, expected_kind="Skill")
        signature = sign_manifest(manifest, SIGNING_KEY)
        self.assertTrue(verify_manifest(manifest, signature, SIGNING_KEY, True))
        self.assertRegex(capability_fingerprint(manifest), r"^sha256:[0-9a-f]{64}$")

    def test_tool_order_does_not_change_permission_equivalence(self):
        manifest = enterprise_skill(tools=["workspace_read", "http_get"])
        validate_capability_manifest(manifest)

    def test_mutating_capability_requires_approval(self):
        manifest = enterprise_skill(mutability="mutating", risk="R3")
        with self.assertRaisesRegex(CapabilityError, "mutating capabilities require approval"):
            validate_capability_manifest(manifest)

    def test_r3_capability_requires_approval(self):
        manifest = enterprise_skill(risk="R3")
        with self.assertRaisesRegex(CapabilityError, "R3-R5 capabilities require approval"):
            validate_capability_manifest(manifest)

    def test_network_allowlist_rejects_wildcards(self):
        manifest = enterprise_skill(
            network_mode="allowlist",
            hosts=["*.example.com"],
        )
        with self.assertRaisesRegex(CapabilityError, "without wildcards"):
            validate_capability_manifest(manifest)

    def test_provenance_requires_sha256_digest(self):
        manifest = enterprise_skill()
        manifest["provenance"]["digest"] = "sha256:not-a-digest"
        with self.assertRaisesRegex(CapabilityError, "provenance.digest"):
            validate_capability_manifest(manifest)

    def test_fingerprint_is_stable_across_dictionary_order(self):
        manifest = enterprise_skill()
        reordered = dict(reversed(list(manifest.items())))
        self.assertEqual(capability_fingerprint(manifest), capability_fingerprint(reordered))

    def test_safe_upgrade_can_reduce_authority(self):
        current = enterprise_skill(
            tools=["workspace_read", "http_get"],
            network_mode="allowlist",
            hosts=["docs.example.com", "api.example.com"],
            timeout_seconds=300,
            visibility="organization",
        )
        candidate = enterprise_skill(
            version="1.0.1",
            tools=["workspace_read"],
            network_mode="allowlist",
            hosts=["docs.example.com"],
            timeout_seconds=120,
            visibility="tenant",
            minimum_score=0.95,
        )
        assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_can_disable_network_access(self):
        current = enterprise_skill(
            network_mode="platform",
        )
        candidate = enterprise_skill(
            version="1.0.1",
            network_mode="deny",
        )
        assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_rejects_tool_expansion(self):
        current = enterprise_skill()
        candidate = enterprise_skill(
            version="1.0.1",
            tools=["workspace_read", "workspace_write"],
        )
        with self.assertRaisesRegex(CapabilityError, "add tool permissions"):
            assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_rejects_visibility_expansion(self):
        current = enterprise_skill(visibility="tenant")
        candidate = enterprise_skill(version="1.0.1", visibility="public")
        with self.assertRaisesRegex(CapabilityError, "broaden capability visibility"):
            assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_rejects_network_mode_change(self):
        current = enterprise_skill(network_mode="platform")
        candidate = enterprise_skill(
            version="1.0.1",
            network_mode="allowlist",
            hosts=["api.example.com"],
        )
        with self.assertRaisesRegex(CapabilityError, "change network authority mode"):
            assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_rejects_approval_weakening(self):
        current = enterprise_skill(
            mutability="mutating",
            risk="R3",
            approval=True,
            minimum_approvals=2,
        )
        candidate = enterprise_skill(
            version="1.0.1",
            mutability="mutating",
            risk="R3",
            approval=True,
            minimum_approvals=1,
        )
        with self.assertRaisesRegex(CapabilityError, "reduce required approvals"):
            assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_rejects_evaluation_removal(self):
        current = enterprise_skill()
        candidate = enterprise_skill(version="1.0.1", evaluation_suite=None)
        with self.assertRaisesRegex(CapabilityError, "remove evaluation requirements"):
            assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_rejects_evaluation_suite_change(self):
        current = enterprise_skill()
        candidate = enterprise_skill(
            version="1.0.1",
            evaluation_suite="different-suite",
        )
        with self.assertRaisesRegex(CapabilityError, "change the evaluation suite"):
            assert_safe_capability_upgrade(current, candidate)

    def test_safe_upgrade_rejects_lower_evaluation_threshold(self):
        current = enterprise_skill(minimum_score=0.9)
        candidate = enterprise_skill(version="1.0.1", minimum_score=0.8)
        with self.assertRaisesRegex(CapabilityError, "lower the evaluation threshold"):
            assert_safe_capability_upgrade(current, candidate)

    def test_remote_registry_rejects_enterprise_authority_expansion(self):
        db = _FakeDB()
        registry = RemoteSkillRegistry(
            db,
            SIGNING_KEY,
            allow_hosts=("registry.example.com",),
        )
        current = enterprise_skill()
        candidate = enterprise_skill(
            version="1.0.1",
            tools=["workspace_read", "workspace_write"],
        )
        packages = [
            {"manifest": current, "signature": sign_manifest(current, SIGNING_KEY)},
            {"manifest": candidate, "signature": sign_manifest(candidate, SIGNING_KEY)},
        ]
        registry._fetch_json = lambda _url: packages.pop(0)

        registry.install(
            "tenant-a",
            "https://registry.example.com/enterprise-review.json",
            "operator-a",
        )
        with self.assertRaisesRegex(SkillRegistryError, "add tool permissions"):
            registry.install(
                "tenant-a",
                "https://registry.example.com/enterprise-review.json",
                "operator-a",
            )
        self.assertEqual("1.0.0", db.get_skill("tenant-a", "enterprise-review")["version"])


if __name__ == "__main__":
    unittest.main()
