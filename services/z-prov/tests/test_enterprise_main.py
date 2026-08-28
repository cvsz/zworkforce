from pathlib import Path

from fastapi.testclient import TestClient
from zeaz_enterprise.main import app


def test_enterprise_health_and_private_replay_state(
    tmp_path: Path, monkeypatch
) -> None:
    state = tmp_path / "private" / "webhooks.sqlite3"
    monkeypatch.setenv("ZEAZ_ENTERPRISE_WEBHOOK_STATE", str(state))
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert app.state.webhook_replay_store is not None
    assert state.exists()
    assert state.stat().st_mode & 0o777 == 0o600
    assert state.parent.stat().st_mode & 0o777 == 0o700
