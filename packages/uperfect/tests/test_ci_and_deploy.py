from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_ci_workflow_runs_supported_checks():
    workflow = read(".github/workflows/ci.yml")

    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "requirements-dev.txt" in workflow
    assert "python -m compileall -q app scripts tests" in workflow
    assert "python -m pytest -q" in workflow
    assert "git diff --check" in workflow


def test_dockerfile_is_non_root_and_matches_runtime_contract():
    dockerfile = read("deploy/Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "uvicorn" in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile
    assert "18765" in dockerfile
    assert "USER uperfect" in dockerfile
    assert "/data" in dockerfile


def test_compose_keeps_the_local_only_network_boundary():
    compose = read("deploy/docker-compose.yml")

    assert '"192.168.74.130:18765:18765"' in compose
    assert 'UPERFECT_LOCAL_ONLY: "true"' in compose
    assert "UPERFECT_LOCAL_AI_BASE_URL: http://192.168.74.130:11434" in compose
    assert "UPERFECT_LOCAL_AI_MODEL: zCoder:latest" in compose
    assert "/api/health" in compose


def test_compose_and_systemd_define_a_separate_notification_worker():
    compose = read("deploy/docker-compose.yml")
    worker_unit = read("deploy/systemd/uperfect-worker.service")

    assert "  worker:" in compose
    assert "app.worker" in compose
    assert "ExecStart=/mnt/uperfect/.venv/bin/python -m app.worker" in worker_unit
    assert "UPERFECT_DATABASE_PATH=/mnt/uperfect/uperfect.db" in worker_unit


def test_nginx_template_routes_only_to_the_documented_origin():
    nginx = read("deploy/nginx/uperfect.conf.example")

    assert "server_name uperfect.zeaz.dev;" in nginx
    assert "server 192.168.74.130:18765;" in nginx
    assert "proxy_pass http://uperfect_app;" in nginx
    assert "ssl_certificate" in nginx
    assert "X-Private-Key" not in nginx
