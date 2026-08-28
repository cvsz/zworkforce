"""
health.py — Liveness/readiness checks for container orchestration

Exposed via `--health-check` (main.py) and used as the Docker HEALTHCHECK
command (see Dockerfile). Deliberately does NOT make a real API call on
every check (that would burn quota / money on every orchestrator probe,
which commonly run every few seconds) — it verifies the things that would
make the process itself unhealthy: config readable, API key present in
some form, disk-writable for config/cache dirs.

For a true end-to-end check against the live API, use `--health-check --deep`
sparingly (e.g. a startup probe run once, not a liveness probe run every 5s).
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

from wire.config import CONFIG_PATH, Config


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class HealthReport:
    checks: list = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @property
    def healthy(self) -> bool:
        return all(c.ok for c in self.checks)

    def to_dict(self) -> dict:
        return {
            "status": "healthy" if self.healthy else "unhealthy",
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


def _check_api_key() -> CheckResult:
    cfg = Config()
    key = cfg.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    return CheckResult("api_key_configured", bool(key), "" if key else "ANTHROPIC_API_KEY not set and no key in config")


def _check_config_writable() -> CheckResult:
    try:
        directory = os.path.dirname(CONFIG_PATH) or "."
        os.makedirs(directory, exist_ok=True)
        probe = os.path.join(directory, ".wire_health_probe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return CheckResult("config_dir_writable", True)
    except Exception as e:
        return CheckResult("config_dir_writable", False, str(e))


def _check_python_version() -> CheckResult:
    ok = sys.version_info >= (3, 9)
    return CheckResult("python_version", ok, f"{sys.version.split()[0]} ({'ok' if ok else 'requires >= 3.9'})")


def _check_live_api(api_key: str, model: str = "zc-xxx") -> CheckResult:
    """Deep check — makes one minimal live call. Only run explicitly."""
    try:
        from wire.coder import Coder
        c = Coder(api_key=api_key, model=model, max_tokens=8)
        result = c.generate("Reply with the single word: ok")
        ok = not str(result).startswith("[ERROR]") and not str(result).startswith("[API ERROR")
        return CheckResult("live_api_call", ok, str(result)[:200])
    except Exception as e:
        return CheckResult("live_api_call", False, str(e))


def run_health_check(deep: bool = False) -> HealthReport:
    report = HealthReport()
    report.checks.append(_check_python_version())
    report.checks.append(_check_config_writable())
    key_check = _check_api_key()
    report.checks.append(key_check)

    if deep and key_check.ok:
        cfg = Config()
        key = cfg.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        report.checks.append(_check_live_api(key))

    return report
