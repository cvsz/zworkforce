from pathlib import Path
import subprocess
import unittest

from botocore.exceptions import ClientError

from zworkforce.s3_errors import is_missing_object_error


ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
WINDOWS_SIGNED_CANDIDATE_WORKFLOW = ROOT / ".github" / "workflows" / "windows-signed-candidate.yml"
EXTERNAL_GATES = ROOT / "scripts" / "close-zworkforce-external-gates.sh"
HA_VERIFIER = ROOT / "scripts" / "release" / "verify-ha.sh"
OBS_VERIFIER = ROOT / "scripts" / "release" / "verify-observability.sh"
WINDOWS_PACKAGE_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Package-Client.ps1"
WINDOWS_TEST_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Test-Client.ps1"
WINDOWS_SIGNATURE_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Verify-MSIXSignature.ps1"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_publish_tolerates_missing_windows_artifact_directory(self):
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("continue-on-error: true", workflow)
        self.assertGreaterEqual(workflow.count("mkdir -p windows-assets"), 2)
        self.assertIn("Windows release artifacts were skipped", workflow)
        self.assertIn("find dist windows-assets -type f -print", workflow)

    def test_release_uses_azure_artifact_signing_with_oidc(self):
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("id-token: write", workflow)
        self.assertIn("uses: azure/login@v3", workflow)
        self.assertIn("uses: azure/artifact-signing-action@v2", workflow)
        self.assertIn("AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}", workflow)
        self.assertIn("AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}", workflow)
        self.assertIn("AZURE_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}", workflow)
        self.assertIn("AZURE_ARTIFACT_SIGNING_ENDPOINT", workflow)
        self.assertIn("AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME", workflow)
        self.assertIn("AZURE_ARTIFACT_SIGNING_PROFILE_NAME", workflow)
        self.assertIn("Package-Client.ps1 -Configuration Release -Platform x64 -Unsigned", workflow)
        self.assertIn("timestamp-rfc3161: http://timestamp.acs.microsoft.com", workflow)
        self.assertIn("timestamp-digest: SHA256", workflow)
        self.assertIn("file-digest: SHA256", workflow)
        self.assertIn("enhanced-key-usage: 1.3.6.1.5.5.7.3.3", workflow)
        self.assertNotIn("WINDOWS_MSIX_PFX_BASE64", workflow)
        self.assertNotIn("Import-PfxCertificate", workflow)

    def test_pre_tag_windows_candidate_signing_is_sha_pinned_and_non_publishing(self):
        workflow = WINDOWS_SIGNED_CANDIDATE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("CANDIDATE_REF", workflow)
        self.assertIn("ref must be a full 40-character commit SHA", workflow)
        self.assertIn("git merge-base --is-ancestor", workflow)
        self.assertIn("environment: production", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("uses: azure/login@v3", workflow)
        self.assertIn("uses: azure/artifact-signing-action@v2", workflow)
        self.assertIn("Package-Client.ps1 -Configuration Release -Platform x64 -Unsigned", workflow)
        self.assertIn('ExpectedVersion "$($env:RELEASE_VERSION).0"', workflow)
        self.assertIn("Upload signed candidate evidence", workflow)
        self.assertNotIn("gh release create", workflow)
        self.assertNotIn("docker/build-push-action", workflow)
        self.assertNotIn("WINDOWS_MSIX_PFX_BASE64", workflow)

    def test_unsigned_windows_package_is_explicit_and_signature_verifier_is_required(self):
        package_script = WINDOWS_PACKAGE_SCRIPT.read_text(encoding="utf-8")
        signature_script = WINDOWS_SIGNATURE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("[switch]$Unsigned", package_script)
        self.assertIn("[string]$Publisher", package_script)
        self.assertIn("AppxPackageSigningEnabled=false", package_script)
        self.assertIn("Verify-MSIXSignature.ps1", signature_script)
        self.assertIn("Get-AuthenticodeSignature -LiteralPath", signature_script)
        self.assertIn('$signature.Status -ne "Valid"', signature_script)
        self.assertIn("TimeStamperCertificate", signature_script)
        self.assertIn("X509Chain", signature_script)
        self.assertIn("AppxSignature.p7x", signature_script)
        self.assertIn("AppxBlockMap.xml", signature_script)
        self.assertIn("Get-ZipEntryByName", signature_script)
        self.assertIn("[IO.Path]::GetFileName", signature_script)
        self.assertIn("Code Signing", signature_script)
        self.assertIn("ExpectedSha256", signature_script)

    def test_external_stage_h_consumes_a_trusted_signed_artifact(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")

        self.assertIn("WINDOWS_MSIX_EXPECTED_SHA256", gates)
        self.assertIn("trusted_signing_artifact_required", gates)
        self.assertIn("Verify-MSIXSignature.ps1", gates)
        self.assertIn("WINDOWS_MSIX_PUBLISHER", gates)
        self.assertNotIn("WINDOWS_MSIX_PFX_PASSWORD", gates)
        self.assertNotIn("WINDOWS_MSIX_SIGNING_PFX_PATH", gates)

    def test_release_policy_requires_azure_artifact_signing(self):
        policy = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("azure/artifact-signing-action@v2", policy)
        self.assertIn("azure/login@v3", policy)
        self.assertIn("Package-Client.ps1 -Unsigned", policy)
        self.assertNotIn("WINDOWS_MSIX_PFX_BASE64", policy)

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
        self.assertIn("[string]$PackagePath", test_script)
        self.assertIn("Get-Item -LiteralPath $PackagePath", test_script)
        self.assertIn("if (-not $SkipTrust) {\n        Assert-Administrator", test_script)

    def test_windows_gate_validates_msix_entries_and_production_certificate_chain(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")
        signature = WINDOWS_SIGNATURE_SCRIPT.read_text(encoding="utf-8")

        for needle in [
            "X509Chain",
            "AppxSignature.p7x",
            "AppxBlockMap.xml",
            "Get-AuthenticodeSignature -LiteralPath",
            '$signature.Status -ne "Valid"',
            "TimeStamperCertificate",
            "Code Signing",
            "ExpectedSha256",
        ]:
            self.assertIn(needle, signature)
        self.assertIn("expectedPublisher", gates)
        self.assertIn("publisher -ne $expectedPublisher", gates)
        self.assertIn("git status --porcelain", gates)
        self.assertIn("ZWorkforceClient/out/Release-x64", gates)
        self.assertIn("expectedPackageVersion", gates)
        self.assertIn('ps_expected_package_version="$(ps_single_quote "$release_version.0")"', gates)
        self.assertNotIn("self-signed", gates)

    def test_windows_gate_reports_signing_blockers_without_powershell_error_prefix(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")

        self.assertIn("(Get-Variable -Name _ -ValueOnly).Exception.Message", gates)
        self.assertNotIn("[string](Get-Variable -Name _ -ValueOnly)", gates)
        self.assertIn("GATE_FAILURE_STATUS=BLOCKED", gates)
        self.assertIn("trusted_signing_artifact_required", gates)
        self.assertNotIn("WINDOWS_MSIX_PFX_PASSWORD", gates)


if __name__ == "__main__":
    unittest.main()
