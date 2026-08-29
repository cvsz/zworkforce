# Security Audit Report — zWorkforce Repository

**Date:** 2026-08-29  
**Scope:** Python source files in `zworkforce/`, `services/`, `packages/zarvis/`, `packages/zider/`, `packages/zksato/`, `automation/`, `scripts/`, `tools/`, `tests/`  
**Method:** Static code analysis via pattern matching and manual code review

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 5     |
| High     | 5     |
| Medium   | 6     |
| Low      | 4     |

**Key architectural note:** The `zworkforce/` core service has strong security boundaries (allowlisted HTTP, sandboxed workspace tools with path confinement, PBKDF2 secret hashing, HMAC-signed proxy identity, tenant-scoped queries). The highest-risk findings are concentrated in the `services/zc/src/wire/` CLI agent subsystem and the `packages/zider/` browser-extension BFF.

---

## CRITICAL Findings

### CRITICAL-1: Arbitrary Shell Command Execution via Bash Tool
**File:** `services/zc/src/wire/zc_code.py:838`  
**Function:** `CodeAgent._run_tool()` — Bash tool branch

```python
cmd = inputs["command"]
...
r = subprocess.run(["/bin/bash", "-c", cmd], shell=False, cwd=cwd,
                   capture_output=True, text=True, timeout=timeout)
```

**Risk:** The Bash tool takes a command string from LLM-generated tool calls and executes it via `/bin/bash -c`. Although `shell=False` is set, passing `["/bin/bash", "-c", cmd]` achieves full shell execution including pipes, redirects, command substitution, and all shell builtins. The optional sandbox (`zc_sandbox.py`, gated behind `AI_CODER_SANDBOX=1`) uses regex-based pattern matching that is trivially bypassable (e.g., `python3 -c "import os;os.system('curl http://x')"` — the URL check regex `https?://` catches some but `python3 -c "..."` with encoded payloads, or non-URL exfiltration, bypasses it). The sandbox is **not enabled by default**.

**Exploit:** A malicious or jailbroken LLM can generate a tool call `{"name":"Bash","inputs":{"command":"cat /etc/shadow"}}` or exfiltrate data via DNS/HTTP.

**Remediation:** 
- Enable the sandbox by default (not opt-in).
- Replace regex-based blocking with an allowlist of permitted command binaries.
- Consider true OS-level isolation (containers/seccomp) rather than pattern-based blocking.

---

### CRITICAL-2: Python Sandbox Escape via Missing Dunder Attribute Checks in `exec()`
**File:** `services/zc/src/wire/zc_excel.py:191` and `services/zc/src/wire/zc_powerpoint.py:236`  
**Function:** `ExcelSession.apply_code()` / `PptxSession.apply_code()`

```python
exec(compile(code, "<excel-turn>", "exec"), {"__builtins__": {
    "len": len, "range": range, "sum": sum, ...
}}, local_ns)
```

```python
_FORBIDDEN_ATTRS = frozenset([
    "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "open", "eval", "exec", "__import__", "compile", "globals",
    "locals", "vars", "dir", "getattr", "setattr", "delattr",
])
```

**Risk:** The AST-based denylist (`_FORBIDDEN_ATTRS`) blocks common dangerous names but omits critical dunder attributes: `__class__`, `__bases__`, `__subclasses__`, `__globals__`, `__builtins__`, `__mro__`, `__base__`, `__dict__`, `__import__`. An attacker can escape the `__builtins__` restriction using the well-known Python sandbox escape:

```python
().__class__.__bases__[0].__subclasses__()
```

This returns all subclasses of `object`, from which `subprocess.Popen`, `os.system`, or `warnings.catch_warnings` (which can access builtins) can be reached. The test file `services/zc/tests/test_restricted_code.py:20` explicitly tests that `(1).__class__.__mro__` should be rejected, but `__class__` is **not** in `_FORBIDDEN_ATTRS`, meaning the test would fail (or the module `wire.restricted_code` that the test imports does not exist — see MEDIUM-5).

**Remediation:**
- Add all dunder attributes to `_FORBIDDEN_ATTRS`.
- Switch from a denylist to an allowlist approach for AST node/attribute validation.
- Consider not using `exec()` at all; parse the model output as structured data instead.

---

### CRITICAL-3: Path Traversal in Read/Write/Edit/Glob/Grep Tool Implementations
**File:** `services/zc/src/wire/zc_code.py:807-822, 848-855, 870`  
**Function:** `CodeAgent._run_tool()` — Read/Write/Edit/Glob/Grep tool branches

```python
if name == "Read":
    p = Path(cwd) / inputs["path"]
    return p.read_text()[:8000]

elif name == "Write":
    p = Path(cwd) / inputs["path"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(inputs["content"])

elif name == "Edit":
    p = Path(cwd) / inputs["path"]
    content = p.read_text()
    ...
    p.write_text(new)

elif name == "Glob":
    base = Path(cwd) / inputs.get("path", ".")
    matches = sorted(base.glob(pattern))

elif name == "Grep":
    base = Path(cwd) / inputs.get("path", ".")
    ...
    for f in base.rglob(include):
```

**Risk:** None of these tools validate or confine the resolved path to `cwd`. An LLM can supply `../../etc/passwd`, `/etc/shadow`, or an absolute path like `/root/.ssh/id_rsa` as the `path` argument. `Path(cwd) / "../../etc/passwd"` resolves outside `cwd`, allowing arbitrary file read and write. The `Glob` and `Grep` tools can enumerate and read files across the entire filesystem.

**Exploit:** Tool call `{"name":"Read","inputs":{"path":"../../etc/passwd"}}` returns the contents of `/etc/passwd`.

**Remediation:**
- Resolve the path and verify it is within `cwd` before any file operation: `resolved = (Path(cwd) / inputs["path"]).resolve(); if not resolved.is_relative_to(Path(cwd).resolve()): raise ToolError("path escapes working directory")`.
- Reject absolute paths and any path containing `..` components.

---

### CRITICAL-4: SSRF via WebFetch Tool
**File:** `services/zc/src/wire/zc_code.py:716-723`  
**Function:** `CodeAgent._webfetch_retrying()`

```python
@retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
def _webfetch_retrying(self, url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ai-coder-agent/1.8"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")[:4000]
    except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
        raise_for_http_error(e)
        raise e
```

**Risk:** The WebFetch tool accepts an arbitrary URL from the LLM and fetches it with no SSRF protections: no allowlist, no private-IP blocking, no redirect validation, no scheme restriction. The fetched content is returned to the LLM, enabling it to probe internal services, read cloud metadata endpoints (`http://169.254.169.254/`), access internal admin panels, or enumerate VPC resources. The comment on line 713 explicitly states "No CircuitBreaker" and shows no SSRF consideration.

**Exploit:** Tool call `{"name":"WebFetch","inputs":{"url":"http://169.254.169.254/latest/meta-data/iam/security-credentials/"}}` returns AWS IAM credentials to the LLM.

**Remediation:**
- Implement URL validation: block private/reserved/loopback/link-local IP ranges, enforce HTTPS-only for external hosts, validate against a host allowlist, and block redirect chains to internal addresses.
- Apply the same SSRF protections already implemented in `zworkforce/tools.py:_validate_url()` (lines 338-355).

---

### CRITICAL-5: Path Traversal in `zc_git.py` `open()` Call
**File:** `services/zc/src/wire/zc_git.py:78-81`  
**Function:** `explain_blame()`

```python
def explain_blame(file: str, line_start: int, line_end: int,
                  cwd: str, api_key: str, model: str) -> str:
    blame = _git(f"git log --oneline {file}", cwd)
    try:
        with open(f"{cwd}/{file}") as f:
            code = "\n".join(f.readlines()[line_start-1:line_end])
    except Exception:
        code = "(could not read file)"
```

**Risk:** The `file` parameter is interpolated into both the git command and the `open()` call without sanitization. While `_git()` uses `shlex.split()` with `shell=False` (preventing shell injection), the `open(f"{cwd}/{file}")` call has no path confinement. A `file` value of `../../etc/passwd` or an absolute path like `/etc/shadow` would read arbitrary files on the filesystem. Additionally, the `_git` function at lines 54-55 and 63 uses f-string interpolation (`f"git log {base}..{head} --oneline"`) where `base`, `head`, and `since_tag` come from CLI arguments — while not shell injection, these are unvalidated arguments passed to git.

**Exploit:** Calling `explain_blame("../../etc/shadow", 1, 10, ".", key, model)` reads `/etc/shadow`.

**Remediation:**
- Validate that `file` is a simple relative path: reject paths containing `..`, absolute paths, and null bytes.
- Use `shlex.quote()` for arguments passed to git commands, or better, use `git` with `--` to separate paths.

---

## HIGH Findings

### HIGH-1: SQL Injection Risk via f-string in PRAGMA Query
**File:** `zworkforce/db_base.py:109`  
**Function:** `DatabaseBase._column_exists()`

```python
rows = c.execute(f"PRAGMA table_info({table})").fetchall()
```

**Risk:** The `table` parameter is interpolated directly into the SQL via f-string. While all current call sites pass hardcoded table names (`"workflow_runs3"`, `"outbox3"`), PRAGMA statements in SQLite do not support parameterized queries for identifiers. If a future caller passes user-controlled input as `table`, it would enable SQL injection. This is a latent vulnerability that violates secure coding practices.

**Remediation:**
- Validate `table` against an allowlist of known table names.
- Use `assert table in ALLOWED_TABLES` before interpolation.

---

### HIGH-2: CORS Wildcard with Credentials in zider BFF
**File:** `packages/zider/server/app/main.py:31-37`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Risk:** The `allow_origins=["*"]` combined with `allow_credentials=True` is a CORS misconfiguration. Per the CORS specification, when credentials are included, the wildcard origin is not valid. In practice, Starlette/FastAPI may silently allow credentialed cross-origin requests from any origin. The zider BFF is designed to proxy AI provider API keys (per the package's AGENTS.md: "Browser extension clients and static frontend assets must NEVER receive raw API provider keys"). Allowing any origin to make credentialed requests means a malicious website could make authenticated requests to the BFF and exfiltrate AI responses containing sensitive data.

**Exploit:** A malicious web page at `evil.com` can make `fetch("https://zider-bff/internal-endpoint", {credentials: "include"})` from a victim's browser.

**Remediation:**
- Replace `allow_origins=["*"]` with an explicit allowlist of trusted extension/web origins.
- Never combine `allow_origins=["*"]` with `allow_credentials=True`.

---

### HIGH-3: Unauthenticated `/metrics` Endpoint
**File:** `services/zc-api/app.py:396` and `services/phase6-api/app.py:396`

```python
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain; version=0.0.4; charset=utf-8")
```

**Risk:** The `/metrics` endpoint is not protected by the `auth` dependency and is accessible to any unauthenticated caller. Prometheus metrics may expose internal state including request counts, latency distributions, provider failure rates, and potentially tenant or deployment identifiers. In the `zc-api` service, all other endpoints require `Bearer {TOKEN}` authentication, but `/metrics` is an exception.

**Remediation:**
- Add `Depends(auth)` to the `/metrics` endpoint, or restrict it to localhost/network-level access.

---

### HIGH-4: CORS Wildcard in Debug Mode
**File:** `services/zc/app/main.py:110`

```python
allow_origins=["*"] if config.debug else ["http://localhost:*"],
```

**Risk:** When `config.debug` is `True`, CORS allows any origin with `allow_credentials=True` (line 111). This is the same CORS misconfiguration pattern as HIGH-2. In debug mode, this could expose authenticated API responses to any origin.

**Remediation:**
- In debug mode, use a specific set of allowed origins rather than `"*"`.

---

### HIGH-5: Environment Variable Injection in Hooks Subprocess
**File:** `services/zc/src/wire/zc_code.py:326-330`  
**Function:** `HooksEngine.fire()`

```python
cmd  = handler.get("command", "")
env  = {**os.environ, **handler.get("env", {})}
...
cmd_args = shlex.split(cmd) if isinstance(cmd, str) else cmd
result = subprocess.run(
    cmd_args, shell=False, input=stdin_data,
    capture_output=True, text=True, timeout=30, env=env,
)
```

**Risk:** The hook subprocess inherits `os.environ` merged with handler-configured environment variables. If a handler's `env` configuration contains sensitive values (or if `os.environ` leaks to the hook), those values could be exfiltrated. Additionally, the `cmd` from handler config is split via `shlex.split` and executed — while not shell injection (since `shell=False`), it allows arbitrary command execution if the handler configuration is attacker-controlled (e.g., through a compromised plugin or config file).

**Remediation:**
- Do not pass `os.environ` to hook subprocesses; instead, explicitly construct a minimal environment.
- Validate handler command names against an allowlist.

---

## MEDIUM Findings

### MEDIUM-1: Information Disclosure via Raw Exception Strings in Error Responses
**Files:** `zworkforce/api.py:222, 355, 370, 584, 586`; `services/zc/src/wire/zc_code.py:711`; `services/zc-api/app.py:113, 199, 228, 252`

```python
# zworkforce/api.py:584-586
except (ValueError,TypeError,SkillError,PolicyError) as exc:
    return self._error(400,"invalid_request",str(exc))
except Exception as exc:
    return self._error(500,"internal_error","internal server error",str(exc))
```

```python
# zc_code.py:711
except Exception as e:
    return {"error": str(e)}
```

**Risk:** Raw exception messages are returned in API error responses (via the `details` field in `_error`, which is included unless `env == "production"`). In production, `str(exc)` for 500 errors is suppressed, but 400-level errors still include `str(exc)` as the message. Internal exception messages from providers, database errors, or stack trace fragments could leak internal implementation details, file paths, or partial credentials.

**Remediation:**
- Log full exception details server-side; return generic error messages to clients.
- For 400-level errors, ensure `str(exc)` only contains user-actionable, non-sensitive information.

---

### MEDIUM-2: Dynamic SQL with String Concatenation for Column Names
**File:** `zworkforce/db_automation.py:197-198`

```python
c.execute("UPDATE workflow_steps3 SET " + ",".join(f"{k}=?" for k, _ in items) +
          " WHERE run_id=? AND step_id=?", tuple(v for _, v in items) + (run_id, step_id))
```

**Risk:** While the column names are filtered through an allowlist (`allowed = {"status", "task_id", "result", "error", "started_at", "finished_at"}`), the dynamic SQL construction pattern is fragile. If the allowlist is modified or bypassed in a future change, it could lead to SQL injection. The same pattern appears in `db_tasks.py:83` for task updates.

**Remediation:**
- Keep the allowlist approach but add a runtime assertion that all column names are in the allowlist.
- Consider using an ORM or query builder that handles dynamic column names safely.

---

### MEDIUM-3: Dynamic SQL in ON CONFLICT Clause
**File:** `zworkforce/db_governance.py:55-57`

```python
conflict_target = "id" if key_id.startswith("bootstrap-") else "key_hash"
c.execute(
    f"""INSERT INTO api_keys2(...) VALUES(?,?,?,?,?,?,0,?)
    ON CONFLICT({conflict_target}) DO UPDATE SET ...""",
    ...
)
```

**Risk:** The `conflict_target` is used in an f-string within the SQL query. While currently limited to two hardcoded values, the pattern is a SQL injection vector if the conditional logic is modified to include user-controlled input.

**Remediation:**
- Validate `conflict_target` against an allowlist: `assert conflict_target in ("id", "key_hash")`.

---

### MEDIUM-4: Missing `restricted_code.py` Module — Security Validation Gap
**File:** `services/zc/tests/test_restricted_code.py:3`

```python
from wire.restricted_code import RestrictedCodeError, validate_restricted_code
```

**Risk:** The test file imports from `wire.restricted_code`, but this module does not exist in the repository (verified via filesystem search). The tests in this file either fail to import or are skipped. This means the intended security validation for restricted code execution (`zc_excel.py` `apply_code`, `zc_powerpoint.py` `apply_code`) is not actually enforced by the missing module. The `_validate_code_ast` methods in `zc_excel.py` and `zc_powerpoint.py` are used instead, but these have the sandbox escape vulnerability described in CRITICAL-2.

**Remediation:**
- Either create the `restricted_code.py` module with a robust allowlist-based validator, or remove the broken test imports and consolidate validation into the existing `_validate_code_ast` methods with all dunder attributes blocked.

---

### MEDIUM-5: Subprocess with PATH-Resolved Executable (Supply Chain Risk)
**File:** `zworkforce/providers.py:94-102`

```python
executable = shutil.which("zktcoder") or shutil.which("zwf-coder") or "/usr/local/bin/zwf-coder"
if not os.path.exists(executable):
    raise ProviderError(...)
proc = subprocess.run([executable], input=prompt_text, ...)
```

**Risk:** The executable is resolved from `PATH` via `shutil.which()`. If an attacker can write to a directory earlier in `PATH` (e.g., `/tmp` if it's in PATH, or a compromised `/usr/local/bin`), they could place a malicious binary that gets executed instead of `zktcoder`/`zwf-coder`. The prompt text is passed as stdin, so the malicious binary would receive all agent conversation data.

**Remediation:**
- Verify the executable's path is an absolute, expected location.
- Pin to a full absolute path rather than relying on `shutil.which()`.
- Consider hashing/verifying the executable before execution.

---

### MEDIUM-6: Error Message Disclosure in `_post()` Error Handling
**File:** `services/zc/src/wire/zc_code.py:710-711`

```python
except Exception as e:
    return {"error": str(e)}
```

**Risk:** The `_post()` method catches all exceptions and returns `str(e)` as an error string. This could leak internal details such as API endpoint URLs, authentication headers, or provider response bodies. The error is then surfaced to the user/LLM in the conversation.

**Remediation:**
- Log the full error server-side and return a generic error message to the user.

---

## LOW Findings

### LOW-1: `shell=True` Referenced in Documentation/Prompt
**File:** `tools/agent_prompt_generator/generator.py:37`

```python
"Never introduce shell=True or expose plaintext secrets.",
```

**Risk:** This is a string literal in a prompt template, not actual code usage. It serves as an instruction to avoid `shell=True`. No actual security issue, but confirms awareness of the risk.

---

### LOW-2: Hardcoded Test Secrets in Test Files
**Files:** `tests/test_acp.py:28`, `tests/test_alert_receiver.py:12`, `services/zc/tests/test_zc_wif.py:253`

```python
# test_acp.py:28
def acp_post(self, body, token="test-admin-secret"):

# test_zc_wif.py:253
long_token = "sk-ant-oat01-" + "x" * 40
```

**Risk:** Test files contain hardcoded test tokens and secrets. These are not production credentials, but they could be used for test environment exploitation if the test infrastructure is exposed. The pattern `sk-ant-oat01-xxxx...` mirrors real Anthropic API key format.

**Remediation:**
- Use environment variables or test fixture factories for test secrets.
- Ensure test files are not accidentally deployed to production.

---

### LOW-3: `random` Module Used for Delay Calculation (Not Security-Critical)
**File:** `zworkforce/providers.py:164, 288` and `packages/zksato/src/zksato/market.py:63-64`

```python
time.sleep(min(0.25 * (2**attempt) + random.random() * 0.1, 3.0))
volume=random.randint(1_000, 100_000)
```

**Risk:** The `random` module (not `secrets`) is used for retry delay jitter and mock market data. This is not a security issue since neither value is security-sensitive (retry delays and simulated data). However, if `random` were ever used for token generation or security-critical values, it would be vulnerable. The codebase correctly uses `secrets` for API keys (`security.py:116`) and canary tokens (`secret_canary.py:25`).

**Remediation:** No action needed — current usage is non-security-critical.

---

### LOW-4: Broad Exception Handling in Hooks Engine
**File:** `services/zc/src/wire/zc_code.py:338-339`

```python
except Exception as e:
    print(f"  \033[91m[hook:{event}] error: {e}\033[0m")
```

**Risk:** The hooks engine catches all exceptions and prints them, potentially leaking environment details or configuration information to the terminal. The exception message could include file paths, environment variables, or internal state.

**Remediation:**
- Log detailed errors to a secure log channel; display only a sanitized message to the user.

---

## Positive Findings (Well-Implemented Security Controls)

1. **`zworkforce/tools.py` — SSRF Protection (lines 338-355, 357-387):** The HTTP tools implement comprehensive SSRF protection including scheme validation, host allowlisting, private IP blocking via DNS resolution checks, and redirect validation through re-validation on each hop.

2. **`zworkforce/tools.py` — Path Traversal Protection (lines 107-117):** The `_safe_path()` method validates paths against the workspace root, rejecting null bytes, absolute paths, `..` traversal, and `%2e` encoded sequences.

3. **`zworkforce/security.py` — PBKDF2 Secret Hashing (lines 150-171):** API key secrets are hashed using PBKDF2-HMAC-SHA256 with 600,000 iterations and random salt, with minimum/maximum iteration validation on verification.

4. **`zworkforce/security.py` — Proxy Identity HMAC Verification (lines 77-99):** Proxy identity headers are HMAC-signed with a 60-second timestamp window and constant-time comparison via `hmac.compare_digest`.

5. **`zworkforce/process_sandbox.py` — Bubblewrap Sandbox (lines 25-211):** Implements Linux namespace isolation with `--unshare-all`, `--cap-drop ALL`, read-only system mounts, tmpfs, and resource limits (CPU, memory, process count, file count).

6. **`deploy/observability/alert_receiver.py` — Bearer Token Authentication (lines 64-69):** Uses `hmac.compare_digest` for constant-time token comparison, validates evidence IDs via regex, and disables access logging to prevent credential leakage.

7. **`zworkforce/skills.py` — HMAC Manifest Verification (lines 23-35):** Skill manifests are verified using HMAC-SHA256 with constant-time comparison.

8. **`zworkforce/worktree.py` — Workspace Path Traversal Protection (lines 102-117):** Path resolution rejects absolute paths, `..` components, and `%2e` encoded sequences, with `resolve(strict=True)` and `relative_to()` containment checks.

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| P0 | Fix exec() sandbox escape in `zc_excel.py`/`zc_powerpoint.py` by adding dunder attributes to the denylist and switching to allowlist validation |
| P0 | Add path traversal protection to `zc_code.py` Read/Write/Edit/Glob/Grep tools |
| P0 | Implement SSRF protection in `zc_code.py` WebFetch tool |
| P0 | Create the missing `wire/restricted_code.py` module or consolidate validation |
| P1 | Add file path sanitization to `zc_git.py` `explain_blame()` |
| P1 | Fix CORS misconfiguration in `zider/server/app/main.py` |
| P1 | Add authentication to `/metrics` in `zc-api/app.py` |
| P1 | Enable sandbox by default in `zc_code.py` Bash tool |
| P2 | Add input validation to dynamic SQL patterns in `db_base.py`, `db_automation.py`, `db_governance.py` |
| P2 | Replace `str(exc)` in error responses with generic messages |
