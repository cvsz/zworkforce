import json

import pytest
from pydantic import ValidationError
from zeaz_enterprise.vault import (
    AWSSecretReference,
    AzureSecretReference,
    GCPSecretReference,
    SecretBinding,
    parse_secret_binding,
)


def test_aws_reference_uses_complete_arn_and_optional_rotation_selector() -> None:
    reference = AWSSecretReference(
        secret_arn=(
            "arn:aws:secretsmanager:us-east-1:123456789012:"
            "secret:production/provider-key-AbCdEf"
        ),
        version_stage="AWSCURRENT",
    )
    binding = SecretBinding(purpose="provider.anthropic", reference=reference)
    assert binding.reference.provider == "aws-secrets-manager"
    assert "value" not in binding.model_dump()


@pytest.mark.parametrize(
    "arn",
    (
        "production/provider-key",
        "arn:aws:secretsmanager:us-east-1::secret:key",
        "arn:aws:s3:us-east-1:123456789012:secret:key",
        "arn:aws:secretsmanager:us-east-1:123456789012:key",
    ),
)
def test_partial_or_wrong_aws_identifiers_are_rejected(arn: str) -> None:
    with pytest.raises(ValidationError):
        AWSSecretReference(secret_arn=arn)


def test_gcp_reference_builds_documented_version_resource() -> None:
    reference = GCPSecretReference(
        project_id="production-123",
        secret_id="anthropic-key",
        version="42",
    )
    assert (
        reference.resource_name
        == "projects/production-123/secrets/anthropic-key/versions/42"
    )


@pytest.mark.parametrize("version", ("", "0", "../latest", "bad/value"))
def test_invalid_gcp_versions_are_rejected(version: str) -> None:
    with pytest.raises(ValidationError):
        GCPSecretReference(
            project_id="production-123",
            secret_id="anthropic-key",
            version=version,
        )


def test_azure_reference_requires_secret_type_and_immutable_version() -> None:
    reference = AzureSecretReference(
        secret_url=(
            "https://example-vault.vault.azure.net/secrets/provider-key/"
            "0123456789abcdef0123456789abcdef"
        )
    )
    assert reference.provider == "azure-key-vault"


@pytest.mark.parametrize(
    "url",
    (
        "http://example-vault.vault.azure.net/secrets/key/0123456789abcdef0123456789abcdef",
        "https://example-vault.vault.azure.net/secrets/key",
        "https://example-vault.vault.azure.net/keys/key/0123456789abcdef0123456789abcdef",
        "https://evil.example/secrets/key/0123456789abcdef0123456789abcdef",
        "https://example-vault.vault.azure.net/secrets/key/0123456789abcdef0123456789abcdef?q=x",
    ),
)
def test_unversioned_or_noncanonical_azure_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        AzureSecretReference(secret_url=url)


def test_untrusted_binding_is_closed_and_round_trips_without_secret_material() -> None:
    raw = {
        "schema_version": "1",
        "purpose": "provider.openai",
        "reference": {
            "provider": "gcp-secret-manager",
            "project_id": "production-123",
            "secret_id": "openai-key",
            "version": "latest",
        },
    }
    binding = parse_secret_binding(raw)
    encoded = binding.model_dump_json()
    assert json.loads(encoded) == raw
    assert all(name not in encoded for name in ("secret_value", "secret_bytes", "token"))

    raw["reference"]["value"] = "must-not-enter-state"
    with pytest.raises(ValidationError):
        parse_secret_binding(raw)


def test_secret_binding_rejects_unknown_provider_and_fields() -> None:
    with pytest.raises(ValidationError):
        parse_secret_binding(
            {
                "schema_version": "1",
                "purpose": "provider.openai",
                "reference": {"provider": "local-file", "path": "/tmp/key"},
            }
        )
    with pytest.raises(ValidationError):
        SecretBinding(
            purpose="provider.openai",
            reference=GCPSecretReference(
                project_id="project",
                secret_id="key",
                version="latest",
            ),
            credential="leak",
        )
