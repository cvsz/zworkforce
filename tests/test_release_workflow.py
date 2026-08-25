from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
EXTERNAL_GATES = ROOT / "scripts" / "close-zworkforce-external-gates.sh"
HA_VERIFIER = ROOT / "scripts" / "release" / "verify-ha.sh"
OBS_VERIFIER = ROOT / "scripts" / "release" / "verify-observability.sh"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_publish_tolerates_missing_windows_artifact_directory(self):
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("continue-on-error: true", workflow)
        self.assertGreaterEqual(workflow.count("mkdir -p windows-assets"), 2)
        self.assertIn("Windows release artifacts were skipped", workflow)
        self.assertIn("find dist windows-assets -type f -print", workflow)

    def test_external_gates_bind_evidence_to_runtime_and_candidate(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")
        ha = HA_VERIFIER.read_text(encoding="utf-8")
        self.assertIn('job_name: "zworkforce-vm-a"', gates)
        self.assertIn('job_name: "zworkforce-vm-b"', gates)
        self.assertIn("credentials_file: \"/run/secrets/metrics-bearer\"", gates)
        self.assertIn('url_file: "/run/secrets/alertmanager-webhook-url"', gates)
        self.assertIn("HA_EXPECTED_IMAGE_DIGEST", gates)
        self.assertIn("ZWORKFORCE_INSTANCE_ID=vm-a", gates)
        self.assertIn("ZWORKFORCE_INSTANCE_ID=vm-b", gates)
        self.assertIn("HA_COMPOSE_FILE_A", ha)
        self.assertIn("HA_COMPOSE_FILE_B", ha)
        self.assertIn('HA_EXPECTED_IMAGE="$HA_EXPECTED_IMAGE"', gates)
        self.assertIn('HA_EXPECTED_IMAGE_DIGEST="$HA_EXPECTED_IMAGE_DIGEST"', gates)
        self.assertIn("exact candidate image", ha)
        self.assertIn("S3 operation=PutObject failed", gates)

    def test_external_gate_shell_boundaries_are_quoted_and_versioned(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")
        observability = OBS_VERIFIER.read_text(encoding="utf-8")
        self.assertIn("-Command -", gates)
        self.assertIn("$PSVersionTable.PSVersion.ToString()", gates)
        self.assertIn("-ExpectedVersion '$release_version.0'", gates)
        self.assertIn("s3={\"addressing_style\": \"path\"}", gates)
        self.assertIn("OBS_COMPOSE_FILE", observability)

    def test_ha_verifier_is_valid_bash(self):
        result = subprocess.run(
            ["bash", "-n", str(HA_VERIFIER)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ha_verifier_uses_project_postgres_dependency(self):
        verifier = HA_VERIFIER.read_text(encoding="utf-8")
        self.assertIn("import psycopg", verifier)
        self.assertNotIn("import psycopg2", verifier)

    def test_ha_verifier_checks_component_lease_ownership(self):
        verifier = HA_VERIFIER.read_text(encoding="utf-8")
        self.assertIn("lease_services=scheduler,outbox", verifier)
        self.assertNotIn("service_leases3 ownership does not match either runtime instance", verifier)

    def test_observability_uses_compose_secrets_and_bounded_target_polling(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")
        verifier = OBS_VERIFIER.read_text(encoding="utf-8")
        self.assertIn("source: metrics-bearer", gates)
        self.assertIn("source: alertmanager-webhook-url", gates)
        self.assertIn("group_add:", gates)
        self.assertIn("OBS_SECRET_GID", gates)
        self.assertNotIn("./metrics-bearer:/etc/prometheus/secrets/metrics-bearer", gates)
        self.assertIn("for _ in $(seq 1 12)", verifier)
        self.assertIn('ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-19093}"', verifier)
        self.assertIn("ALERTMANAGER_PORT=9093 OBS_COMPOSE_FILE=compose.yml", gates)


if __name__ == "__main__":
    unittest.main()
