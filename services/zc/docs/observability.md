# Observability

wire has two, complementary layers of observability. This pass added
the first; the second predates it and is unchanged.

## 1. Process-level structured logs (`logging_config.py`) — new

Every log line the process emits (retries, circuit-breaker state changes,
auth failures, refusals, unexpected exceptions) goes through
`logging_config.py`:

- **Format**: `text` on an interactive TTY, `json` otherwise, or forced
  via `wire_LOG_FORMAT`. JSON lines are one object each — no multi-line
  records to worry about for log shippers.
- **Correlation ID**: one per CLI invocation (`main.py` calls
  `new_correlation_id()` at startup), attached to every line automatically
  so you can filter one invocation's logs out of a shared stream.
- **Redaction**: `RedactingFilter` scrubs `sk-ant-...` key shapes and
  `Authorization`/`x-api-key`/`ZC_API_KEY`-shaped values from every
  record, regardless of what a call site logs.
- **Where it goes**: stderr only, by design — stdout stays reserved for
  the actual CLI output (model responses, `--health-check` JSON, etc) so
  piping `wire -p "..." > out.txt` doesn't get log noise mixed in.

Ship stderr to whatever you already use (CloudWatch Logs agent, Datadog
Agent, Fluent Bit, `journald` under systemd, Docker's default json-file
driver, etc) — no code changes needed, it's already structured JSON when
not attached to a TTY.

### Adding logging to a new module

```python
from logging_config import get_logger
logger = get_logger("my_module")   # -> "wire.my_module"

logger.info("thing_happened", extra={"key": "value"})
logger.error("thing_failed", extra={"error_code": exc.error_code})
```

Use `extra={...}` for structured fields, not f-string interpolation —
that's what makes the JSON output queryable by field instead of requiring
regex over a message string.

## 2. Application-level usage & request logs — pre-existing, unchanged

- **`zc_metrics.py`** (`--metrics-show`, `--metrics-today`,
  `--metrics-model`, `--metrics-export`) — per-call token counts, cost
  (against a verified pricing table), and latency, logged to
  `~/.ai-coder/metrics.jsonl`. Answers "what am I spending, on which
  model."
- **`zc_observability.py`** — structured request/response logging,
  latency histograms, and AI-assisted error-trend analysis, logged to
  `~/.ai-coder/observability/requests.jsonl`. Answers "is latency/error
  rate drifting."

These two answer *product* questions (cost, model comparison, error
trends over days); `logging_config.py` answers *operational* questions
(is this specific process healthy right now, what happened during this
one invocation). Both are useful; neither replaces the other.

## Alerting suggestions

Alert on these JSON log fields from the process-level logs:

| Field/message | Meaning | Suggested action |
|---|---|---|
| `circuit_breaker_open` | 5+ consecutive upstream failures | Page if sustained > a few minutes |
| `rate_limited_after_retries` | 429s exhausted all retry attempts | Check request volume vs. plan limits |
| `auth_failed` | 401 from the API | Key rotated/revoked — not a transient issue |
| `unexpected_error` | An exception outside the typed hierarchy | File a bug; this bypassed the retry/error taxonomy entirely |
