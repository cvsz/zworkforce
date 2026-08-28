from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_compose_profile_is_credential_and_state_isolated() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    service = compose["services"]["enterprise"]
    assert service["profiles"] == ["enterprise"]
    assert "env_file" not in service
    assert service["environment"] == {
        "ZEAZ_ENTERPRISE_WEBHOOK_STATE": (
            "/var/lib/zeaz-enterprise/webhook-replay.sqlite3"
        )
    }
    assert service["volumes"] == [
        "enterprise-state:/var/lib/zeaz-enterprise"
    ]
    assert service["networks"] == ["enterprise"]
    assert service["ports"] == [
        "127.0.0.1:${ZEAZ_ENTERPRISE_PORT:-8091}:8091"
    ]
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert "enterprise-state" in compose["volumes"]
    assert compose["networks"]["enterprise"] == {"internal": False}
    assert set(service["networks"]).isdisjoint(
        compose["services"]["control"]["networks"]
    )
    assert set(service["volumes"]).isdisjoint(
        compose["services"]["control"]["volumes"]
    )


def test_enterprise_image_is_pinned_and_runs_as_dedicated_non_root_user() -> None:
    dockerfile = (ROOT / "Dockerfile.enterprise").read_text()
    pinned = (
        "python:3.12-slim-bookworm@sha256:"
        "d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b"
    )
    assert dockerfile.count(f"FROM {pinned}") == 2
    assert "useradd --uid 10003" in dockerfile
    assert "USER zeaz-enterprise" in dockerfile
    assert 'ENTRYPOINT ["zeaz-enterprise"]' in dockerfile
    assert "COPY . " not in dockerfile
