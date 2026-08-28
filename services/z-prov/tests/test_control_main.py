from pathlib import Path

from fastapi.testclient import TestClient
from zeaz_control.main import app


def test_control_process_has_private_state_and_health(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = tmp_path / "control-state" / "control.sqlite3"
    monkeypatch.setenv("ZEAZ_CONTROL_STATE", str(state))
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/ready").json() == {"status": "ready"}
    assert state.stat().st_mode & 0o777 == 0o600
    assert state.parent.stat().st_mode & 0o777 == 0o700
