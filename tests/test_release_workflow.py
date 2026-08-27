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
OBS_RENDER_CONFIG = ROOT / "deploy" / "observability" / "render-config.sh"
OBS_COMPOSE = ROOT / "deploy" / "observability" / "compose.vm-b.yaml"
OBS_ALERTMANAGER = ROOT / "deploy" / "observability" / "alertmanager.vm-b.yaml"
ALERT_RECEIVER_SERVICE = ROOT / "deploy" / "observability" / "alert-receiver.service"
WINDOWS_PACKAGE_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Package-Client.ps1"
WINDOWS_TEST_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Test-Client.ps1"
WINDOWS_SIGNATURE_SCRIPT = ROOT / "ZWorkforceClient" / "build" / "windows" / "Verify-MSIXSignature.ps1"
POSTGRES_BACKUP_SCRIPT = ROOT / "scripts" / "backup-postgres.sh"
POSTGRES_RESTORE_SCRIPT = ROOT / "scripts" / "restore-postgres.sh"
POSTGRES_CONNECTION_HELPER = ROOT / "scripts" / "lib" / "postgres-connection.sh"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_postgres_backup_and_restore_keep_dsn_out_of_process_arguments(self):
        helper = POSTGRES_CONNECTION_HELPER.read_text(encoding="utf-8")
        self.assertIn("PGSERVICEFILE", helper)
        self.assertIn("PGSERVICE=zworkforce", helper)
        self.assertIn("chmod 600", helper)

        for script_path in (POSTGRES_BACKUP_SCRIPT, POSTGRES_RESTORE_SCRIPT):
            script = script_path.read_text(encoding="utf-8")
            self.assertIn("postgres_configure_service", script)
            self.assertNotIn('"$ZWORKFORCE_DATABASE_URL"', script)

    def test_postgres_backup_and_restore_allow_dedicated_connection_urls(self):
        backup = POSTGRES_BACKUP_SCRIPT.read_text(encoding="utf-8")
        restore = POSTGRES_RESTORE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("ZWORKFORCE_BACKUP_DATABASE_URL", backup)
        self.assertIn("ZWORKFORCE_RESTORE_DATABASE_URL", restore)

    def test_postgres_connection_helper_rejects_encoded_service_file_controls(self):
        probe = """
set -Eeuo pipefail
source "$1"
postgres_configure_service "$2"
postgres_cleanup_service
"""
        for database_url in (
            "postgresql://svc:p%0Ass@127.0.0.1:5432/workforce",
            "postgresql://svc:p%5Css@127.0.0.1:5432/workforce",
        ):
            result = subprocess.run(
                ["bash", "-c", probe, "postgres-connection-probe", str(POSTGRES_CONNECTION_HELPER), database_url],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_publish_tolerates_missing_windows_artifact_directory(self):
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("continue-on-error: true", workflow)
        self.assertGreaterEqual(workflow.count("mkdir -p windows-assets"), 2)
        self.assertIn("Windows release artifacts were skipped", workflow)
        self.assertIn("find dist windows-assets -type f -print", workflow)

    def test_release_uses_azure_artifact_signing_with_oidc(self):
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("id-token: write", workflow)
        self.assertIn("environment: production", workflow)
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
        self.assertIn("CANDIDATE_SHA=$env:CANDIDATE_SHA", workflow)
        self.assertIn("VERSION=$($env:RELEASE_VERSION).0", workflow)
        self.assertIn("PACKAGE=$($package.Name)", workflow)
        self.assertIn("SHA256=$hash", workflow)
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
        self.assertIn("candidateMetadataPath", gates)
        self.assertIn("expectedCandidateSha", gates)
        self.assertIn('"CANDIDATE_SHA", "VERSION", "PACKAGE", "SHA256"', gates)
        self.assertIn("candidate metadata does not match the frozen candidate SHA", gates)
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
        self.assertIn('HA_EXPECTED_IMAGE_PROVENANCE_SHA256', gates)
        self.assertIn('HA_IMAGE_PROVENANCE_FILE', ha)
        self.assertIn('preloaded image provenance hash', ha)
        self.assertIn('HA_EXPECTED_DB_PROJECT_REF', ha)
        self.assertIn('HA_EXPECTED_DB_HOST', ha)
        self.assertIn('HA_EXPECTED_DB_PORT', ha)
        self.assertIn('database_target=PASS', ha)
        self.assertIn('sslmode', ha)
        self.assertIn('HA_EXPECTED_DB_PROJECT_REF="$expected_db_project_ref"', gates)
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

    def test_ha_verifier_proves_both_replicas_share_postgres(self):
        verifier = HA_VERIFIER.read_text(encoding="utf-8")
        self.assertIn("release_ha_probe_", verifier)
        self.assertIn("shared PostgreSQL database", verifier)
        self.assertIn("schema_meta", verifier)

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
        self.assertIn("json.load(sys.stdin)", verifier)
        self.assertIn('record.get("evidence_id")', verifier)
        self.assertIn('record.get("received_at")', verifier)
        self.assertIn('record.get("alert_count")', verifier)
        self.assertIn('record.get("payload_sha256")', verifier)
        self.assertIn('RECEIPT_MAX_CLOCK_SKEW_SECONDS="${RECEIPT_MAX_CLOCK_SKEW_SECONDS:-60}"', verifier)
        self.assertIn("received.timestamp() < submitted_at - max_clock_skew", verifier)
        self.assertIn("RECEIPT_MAX_CLOCK_SKEW_SECONDS must be an integer from 0 through 300", verifier)
        self.assertNotIn("received.timestamp() <= submitted_at", verifier)
        self.assertNotIn("otelcol_receiver_accepted_spans", verifier)
        self.assertIn("trace ID in collector logs", verifier)
        self.assertIn("verbosity: detailed", gates)
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
        self.assertIn("Start-Job -ScriptBlock", test_script)
        self.assertIn("Wait-Job -Job $installJob -Timeout 180", test_script)
        self.assertIn("Stop-Job -Job $installJob", test_script)

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

    def test_observability_receipt_service_prepares_writable_state_before_sandbox(self):
        service = ALERT_RECEIVER_SERVICE.read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=-/etc/zworkforce-observability/alert-receiver.env", service)
        self.assertIn("ExecStartPre=/usr/bin/test -n ${ALERT_RECEIVER_BIND}", service)
        self.assertIn("ExecStartPre=/usr/bin/test -r ${ALERT_RECEIVER_TOKEN_FILE}", service)
        self.assertNotIn("ALERT_RECEIVER_TOKEN_FILE=/opt/zworkforce-observability/alert-receiver-token", service)
        self.assertNotIn("Environment=ALERT_RECEIVER_BIND=192.168.74.134", service)
        self.assertIn("StateDirectory=zworkforce-observability", service)
        self.assertIn("StateDirectoryMode=0700", service)
        self.assertIn("ExecStartPre=/usr/bin/install -d -m 700", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("/var/lib/zworkforce-observability/alert-receipts", service)

    def test_observability_compose_and_renderer_use_protected_receiver_auth(self):
        compose = OBS_COMPOSE.read_text(encoding="utf-8")
        renderer = OBS_RENDER_CONFIG.read_text(encoding="utf-8")
        alertmanager = OBS_ALERTMANAGER.read_text(encoding="utf-8")
        self.assertIn("file: ${ALERT_RECEIVER_TOKEN_FILE:?set ALERT_RECEIVER_TOKEN_FILE}", compose)
        self.assertIn("source: alert-receiver-auth", compose)
        self.assertIn('credentials_file: "/run/secrets/alert-receiver-auth"', renderer)
        self.assertIn('credentials_file: "/run/secrets/alert-receiver-auth"', alertmanager)
        self.assertIn('ALERT_RECEIVER_TOKEN_FILE:?set ALERT_RECEIVER_TOKEN_FILE', renderer)
        self.assertIn('[[ -r "$ALERT_RECEIVER_TOKEN_FILE" ]]', renderer)

    def test_windows_gate_reports_signing_blockers_without_powershell_error_prefix(self):
        gates = EXTERNAL_GATES.read_text(encoding="utf-8")

        self.assertIn("(Get-Variable -Name _ -ValueOnly).Exception.Message", gates)
        self.assertNotIn("[string](Get-Variable -Name _ -ValueOnly)", gates)
        self.assertIn("GATE_FAILURE_STATUS=BLOCKED", gates)
        self.assertIn("trusted_signing_artifact_required", gates)
        self.assertNotIn("WINDOWS_MSIX_PFX_PASSWORD", gates)


if __name__ == "__main__":
    unittest.main()
