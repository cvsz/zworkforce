# v1.13.0 — Enterprise hardening

No CLI flags were removed or renamed; `--health-check`/`--health-check-deep`
are the only additions to the argument surface. Every change below is
additive infrastructure plus internal wiring in `coder.py`/`main.py`.

## New modules

- **`exceptions.py`** — `AICoderError` hierarchy (`ConfigError`,
  `AuthenticationError`, `RateLimitError`, `TransientAPIError`, `APIError`,
  `RefusalError`, `ValidationError`, `SecurityError`, `CircuitOpenError`),
  each with a stable `error_code` and a `RETRYABLE` flag.
- **`resilience.py`** — `retry()` decorator (exponential backoff with full
  jitter, honors a `RateLimitError.retry_after` when present) and
  `CircuitBreaker` (closed/open/half-open). Dependency-free stdlib only.
- **`logging_config.py`** — structured logging (`text` on a TTY, `json`
  otherwise or via `wire_LOG_FORMAT`), a per-invocation correlation ID,
  and automatic redaction of API-key-shaped strings from every log line.
- **`security.py`** — `safe_resolve()` / `validate_name()` (path
  traversal guards), `validate_url()` (https-only), `check_file_size()`
  (default 25MB cap, `wire_MAX_FILE_SIZE_BYTES`), `contains_secret()` /
  `assert_no_secret()`.
- **`health.py`** — `run_health_check(deep=False)`: python version, config
  dir writable, API key present; `deep=True` additionally makes one live
  API call. Backs the new `--health-check` / `--health-check-deep` flags.

## Changed

- **`coder.py`**: `Coder.generate()`'s network call is now wrapped in
  `resilience.retry()` with a shared `CircuitBreaker`. 401s and other 4xxs
  fail immediately (not retried); 429/5xx/network errors retry up to 4
  attempts with backoff. The function's *return contract is unchanged* —
  it still returns `"[ERROR] ..."` / `"[API ERROR N] ..."` /
  `"[REFUSED] ..."` strings rather than raising, so no call site in
  `main.py` or any `zc_*.py` module needed to change. See
  `ARCHITECTURE.md` for why.
- **`main.py`**: calls `logging_config.setup_logging()` and
  `new_correlation_id()` at the top of `main()`, before argument dispatch.

## New: testing, CI, and deployment scaffolding

- `tests/` — pytest suite for `config.py`, `utils.py`, `resilience.py`,
  `security.py`, `logging_config.py`, and `coder.py` (network fully
  mocked, no real API calls in CI).
- `pyproject.toml` — pytest, coverage (70% floor), ruff, black, mypy config.
- `requirements-dev.txt` — pytest, pytest-cov, ruff, black, mypy, bandit.
- `.github/workflows/ci.yml` — lint + bandit + pytest matrix (3.9–3.12) +
  Docker build smoke test, on every push/PR.
- `Dockerfile` (multi-stage, non-root `wire` user, `HEALTHCHECK` wired
  to `--health-check`) + `.dockerignore` + `docker-compose.yml`.
- `Makefile` — `make check` runs lint + typecheck + security + tests.
- `SECURITY.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`,
  `docs/deployment.md`, `docs/observability.md`.
- `.gitignore` (was missing entirely before this release).

## Not done in this pass (flagged for follow-up)

- `resilience.retry()` is only wired into `coder.py`. Other modules that
  make direct HTTP calls (`zc_files.py`, `zc_batch.py`,
  `zc_github.py`, etc.) still have their own ad hoc error handling and
  would benefit from the same wrapper — left alone here to keep this
  release's diff reviewable rather than touching every network call site
  in the same pass.
- No concurrent-writer protection was added for the local JSON state files
  (`~/.ai-coder/projects.json` etc). Not new to this release, but worth
  flagging: two CLI invocations writing the same project at once can race.
- `mypy` is configured but the existing modules aren't type-annotated
  throughout; `make typecheck` will report a large baseline of
  `ignore_missing_imports`-suppressed gaps rather than a clean pass.
