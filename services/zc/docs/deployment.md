# Deployment Guide

## Configuration

All configuration is via environment variables (preferred for production)
or `~/.ai-coder-config.json` (fine for local dev; see `SECURITY.md` for
why env vars are preferred).

| Variable                    | Required | Default | Purpose |
|------------------------------|----------|---------|---------|
| `ANTHROPIC_API_KEY`          | yes      | —       | Anthropic API key |
| `GITHUB_TOKEN`                | no       | —       | `zc_github.py` integration |
| `VOYAGE_API_KEY`              | no       | —       | `zc_embeddings.py` |
| `wire_LOG_LEVEL`            | no       | `INFO`  | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `wire_LOG_FORMAT`           | no       | `text` (TTY) / `json` (non-TTY) | Force `json` or `text` |
| `wire_MAX_FILE_SIZE_BYTES`  | no       | `26214400` (25MB) | Upper bound for `--file`/`--file-upload` |

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ZC_API_KEY=sk-ant-...
python main.py -p "explain this repo"
```

## Running the test suite

```bash
pip install -r requirements-dev.txt
pytest                       # run tests
pytest --cov                 # with coverage
ruff check .                 # lint
black --check .              # format check
bandit -r . -x ./tests       # security static analysis
```

## Running in Docker

```bash
docker build -t wire .
docker run --rm -e ANTHROPIC_API_KEY=sk-ant-... wire -p "hello"

# or via compose (reads ANTHROPIC_API_KEY from the environment or a .env file)
docker compose run --rm wire -p "hello"
```

The image runs as a non-root user, has a `HEALTHCHECK` wired to
`--health-check`, and never bakes `.env`/secrets into layers (see
`.dockerignore`).

## Health checks

```bash
python main.py --health-check          # fast: config + key presence only
python main.py --health-check --deep   # also makes one minimal live API call
```

Exit code `0` = healthy, `1` = unhealthy. Output is JSON:

```json
{
  "status": "healthy",
  "checks": [
    {"name": "python_version", "ok": true, "detail": "3.12.3 (ok)"},
    {"name": "config_dir_writable", "ok": true, "detail": ""},
    {"name": "api_key_configured", "ok": true, "detail": ""}
  ]
}
```

Use the fast check as a container liveness/readiness probe (it's cheap —
no network call). Use `--deep` only for a startup probe or manual
diagnosis; it makes a real, billed API call.

## Logging & observability

Set `wire_LOG_FORMAT=json` in any non-interactive environment (this is
the default when stdout isn't a TTY, e.g. under Docker/systemd/CI) to get
one JSON object per log line, suitable for shipping to a log aggregator
(CloudWatch, Datadog, ELK, etc). Every line carries a `correlation_id`
that's stable for the lifetime of one CLI invocation, so you can trace a
single `--agent-orchestrate` run's log lines across modules.

API keys, `Authorization`/`x-api-key` header values, and known env var
names (`ZC_API_KEY`, `GITHUB_TOKEN`, `VOYAGE_API_KEY`) are redacted
automatically before any log line is emitted — see `logging_config.py`.

See `docs/observability.md` for metrics/tracing hooks (`zc_metrics.py`,
`zc_observability.py`) that predate this pass and remain unchanged.

## Rollback

Every release is tagged. To roll back a container deployment:

```bash
docker pull wire:<previous-tag>
docker compose up -d
```

Config/state on the `wire-home` volume is forward/backward compatible
within a major version (flat JSON files, no schema migrations as of
1.12.x).

## Incident response quick reference

| Symptom | Likely cause | First step |
|---|---|---|
| `--health-check` exits 1, `api_key_configured: false` | Env var not propagated to container | Check `docker inspect` env, secrets manager wiring |
| Every call returns `[API ERROR 429]` | Rate limited, retries exhausted | Check `retry_after` in logs; consider `--service-tier auto` if you have a Priority Tier commitment |
| Every call returns `[API ERROR 401]` | Key rotated/revoked | Rotate key in secrets manager, redeploy |
| Circuit breaker open (`circuit_breaker_open` in logs) | Sustained upstream errors | Check ZaiCoder status page before assuming a local bug |
