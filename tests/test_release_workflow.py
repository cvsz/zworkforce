from pathlib import Path
import subprocess
import unittest

from botocore.exceptions import ClientError

from zworkforce.s3_errors import is_missing_object_error


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
EXTERNAL_GATES = ROOT / "scripts" / "close-zworkforce-external-gates.sh"
HA_VERIFIER = ROOT / "scripts" / "release" / "verify-ha.sh"
OBS_VERIFIER = ROOT / "scripts" / "release" / "verify-observability.sh"
WINDOWS_PACKAGE_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Package-Client.ps1"
WINDOWS_TEST_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Test-Client.ps1"


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
        self.assertIn('credentials_file: "/run/secrets/alert-receiver-auth"', gates)
        self.assertIn('group_by: ["alertname", "evidence_id"]', gates)
        self.assertIn("HA_EXPECTED_IMAGE_DIGEST", gates)
        self.assertIn("ZWORKFORCE_INSTANCE_ID=vm-a", gates)
        self.assertIn("ZWORKFORCE_INSTANCE_ID=vm-b", gates)
        self.assertIn("HA_COMPOSE_FILE_A", ha)
        self.assertIn("HA_COMPOSE_FILE_B", ha)
        self.assertIn('HA_EXPECTED_IMAGE="$HA_EXPECTED_IMAGE"', gates)
        self.assertIn('HA_EXPECTED_IMAGE_DIGEST="$HA_EXPECTED_IMAGE_DIGEST"', gates)
        self.assertIn('HA_IMAGE_PULL_POLICY', gates)
        self.assertIn('docker compose -f \'$compose_a\' up -d --pull never', gates)
        self.assertIn('docker compose -f \'$compose_b\' up -d --pull never', gates)
        self.assertIn("exact candidate image", ha)
        self.assertIn("S3 operation=PutObject failed", gates)

    def test_supabase_missing_object_accepts_status_only_errors(self):
        def client_error(code, status):
            return ClientError(
                {
                    "Error": {"Code": code},
                    "ResponseMetadata": {"HTTPStatusCode": status},
                },
                "GetObject",
            )

        self.assertTrue(is_missing_object_error(client_error("", 403)))
        self.assertTrue(is_missing_object_error(client_error("", 404)))
        self.assertTrue(is_missing_object_error(client_error("NoSuchKey", 404)))
        self.assertTrue(is_missing_object_error(client_error("AccessDenied", 403)))
        self.assertFalse(is_missing_object_error(client_error("InvalidAccessKeyId", 403)))
        self.assertFalse(is_missing_object_error(client_error("NoSuchBucket", 404)))

    def test_external_gate_shell_boundaries_are_quoted_and_versioned(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")
        observability = OBS_VERIFIER.read_text(encoding="utf-8")
        self.assertIn('-Command "Set-Variable -Name ErrorActionPreference', gates)
        self.assertNotIn("pwsh -NoProfile -NonInteractive -Command -", gates)
        self.assertIn("[scriptblock]::Create([Console]::In.ReadToEnd())", gates)
        self.assertIn("(Get-Variable -Name _ -ValueOnly).Exception.Message", gates)
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
        self.assertIn("source: alert-receiver-auth", gates)
        self.assertIn("group_add:", gates)
        self.assertIn("OBS_SECRET_GID", gates)
        self.assertNotIn("./metrics-bearer:/etc/prometheus/secrets/metrics-bearer", gates)
        self.assertIn("for _ in $(seq 1 12)", verifier)
        self.assertIn('ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-19093}"', verifier)
        self.assertIn('ALERT_RECEIVER_TOKEN_FILE="${ALERT_RECEIVER_TOKEN_FILE:', verifier)
        self.assertIn("Authorization: Bearer %s", verifier)
        self.assertIn("otelcol_receiver_accepted_spans", verifier)
        self.assertIn('port: 8888', gates)
        self.assertIn("up -d --force-recreate otel-collector", gates)
        self.assertIn("docker exec zworkforce-observability-alertmanager-1", gates)
        self.assertIn("ALERTMANAGER_PORT=9093 OBS_COMPOSE_FILE=compose.yml", gates)

    def test_windows_live_endpoint_uses_one_powershell_quoted_literal(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")
        self.assertIn(
            'ps_health_endpoint="$(ps_single_quote "$ZWORKFORCE_HTTPS_ENDPOINT/health")"',
            gates,
        )
        self.assertIn(
            'run_h_remote windows_live_endpoint_failed "Invoke-WebRequest -UseBasicParsing $ps_health_endpoint',
            gates,
        )
        self.assertNotIn(
            "Invoke-WebRequest -UseBasicParsing '$(ps_single_quote",
            gates,
        )

    def test_ha_metrics_bearer_is_streamed_over_ssh_stdin(self):
        verifier = HA_VERIFIER.read_text(encoding="utf-8")
        self.assertIn('IFS= read -r metrics_bearer', verifier)
        self.assertIn('metrics_bearer', verifier)
        self.assertNotIn('Authorization: Bearer $ZWORKFORCE_METRICS_BEARER', verifier)
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")
        self.assertIn('-H @-', gates)
        self.assertNotIn('curl -fsS -H "Authorization: Bearer $ZWORKFORCE_METRICS_BEARER"', gates)

    def test_windows_external_pfx_is_available_to_msbuild_certificate_lookup(self):
        package_script = WINDOWS_PACKAGE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Import-PfxCertificate", package_script)
        self.assertIn("Cert:\\CurrentUser\\My", package_script)
        self.assertIn("PackageCertificateThumbprint", package_script)
        self.assertIn("importedSigningCertificateThumbprints", package_script)
        self.assertIn("Remove-Item -LiteralPath", package_script)

    def test_windows_launch_smoke_handoffs_session_zero_to_active_user(self):
        test_script = WINDOWS_TEST_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Register-ScheduledTask", test_script)
        self.assertIn("New-ScheduledTaskPrincipal", test_script)
        self.assertIn("-LogonType Interactive", test_script)
        self.assertIn("SessionId", test_script)
        self.assertIn("InteractiveSmokeWorker", test_script)
        self.assertIn("Start-ScheduledTask", test_script)

    def test_windows_gate_validates_msix_entries_and_production_certificate_chain(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")

        self.assertIn("X509Chain", gates)
        self.assertIn("AppxSignature.p7x", gates)
        self.assertIn("AppxBlockMap.xml", gates)
        self.assertIn("expectedPublisher", gates)
        self.assertIn("publisher -ne $expectedPublisher", gates)
        self.assertIn("git status --porcelain", gates)
        self.assertIn("ZWorkforceClient/out/Release-x64", gates)
        self.assertIn("expectedPackageVersion", gates)
        self.assertIn('ps_expected_package_version="$(ps_single_quote "$release_version.0")"', gates)
        self.assertIn("Get-FileHash -Algorithm SHA256 -LiteralPath $pkg.FullName", gates)
        self.assertIn("self-signed", gates)
        self.assertNotIn("Get-AuthenticodeSignature $pkg", gates)

    def test_windows_gate_reports_signing_blockers_without_powershell_error_prefix(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")

        self.assertIn("(Get-Variable -Name _ -ValueOnly).Exception.Message", gates)
        self.assertNotIn("[string](Get-Variable -Name _ -ValueOnly)", gates)
        self.assertIn("GATE_FAILURE_STATUS=BLOCKED", gates)
        self.assertIn("trusted_signing_certificate_required", gates)


if __name__ == "__main__":
    unittest.main()
