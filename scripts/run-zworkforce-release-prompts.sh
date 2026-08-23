#!/usr/bin/env bash
set -Eeuo pipefail

# zWorkforce v3.0.3 Final External-Evidence Runner v3 — NVIDIA NIM
#
# Canonical repo/path:
#   GitHub: cvsz/zworkforce
#   Local:  /home/cvsz/zworkforce
#
# NVIDIA:
#   Endpoint: https://integrate.api.nvidia.com/v1/chat/completions
#   Model:    nvidia/nemotron-3-ultra-550b-a55b
#
# Required:
#   export NVIDIA_API_KEY='...'
#
# Safety:
# - origin/main is the frozen release-candidate authority.
# - remote matching is case-insensitive.
# - side branches such as evidence-update-main do not invalidate origin/main.
# - NIM is used through an embedded tool-execution loop.
# - shell commands are executed only inside /home/cvsz/zworkforce.
# - destructive/release-publication commands are blocked by default.
# - Stage I is blocked until F/E/G/H/RC PASS markers exist.
# - GO_DECISION=GO is necessary but not sufficient for Stage I.
# - this runner DOES NOT tag/publish v3.0.3 automatically.

FROZEN_CANDIDATE="${FROZEN_CANDIDATE:-d74ec63079caeb7ab270de799b277b1c17367fab}"
REPO_DIR="${REPO_DIR:-/home/cvsz/zworkforce}"
LOG_ROOT="${LOG_ROOT:-$REPO_DIR/.release-evidence-logs}"
STATE_DIR="${STATE_DIR:-$REPO_DIR/.release-evidence-state}"

NVIDIA_ENDPOINT="${NVIDIA_ENDPOINT:-https://integrate.api.nvidia.com/v1/chat/completions}"
NVIDIA_MODEL="${NVIDIA_MODEL:-nvidia/nemotron-3-ultra-550b-a55b}"
NVIDIA_MAX_TOKENS="${NVIDIA_MAX_TOKENS:-8192}"
NVIDIA_TEMPERATURE="${NVIDIA_TEMPERATURE:-0.1}"
NVIDIA_MAX_TOOL_ROUNDS="${NVIDIA_MAX_TOOL_ROUNDS:-24}"
COMMAND_TIMEOUT_SECONDS="${COMMAND_TIMEOUT_SECONDS:-120}"

ALLOW_CANDIDATE_DRIFT="${ALLOW_CANDIDATE_DRIFT:-0}"
ALLOW_DIRTY_WORKTREE="${ALLOW_DIRTY_WORKTREE:-1}"

mkdir -p "$LOG_ROOT" "$STATE_DIR"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

usage() {
  cat <<'EOF'
Usage:
  scripts/run-zworkforce-release-prompts-v3.sh verify
  scripts/run-zworkforce-release-prompts-v3.sh status
  scripts/run-zworkforce-release-prompts-v3.sh F
  scripts/run-zworkforce-release-prompts-v3.sh E
  scripts/run-zworkforce-release-prompts-v3.sh G
  scripts/run-zworkforce-release-prompts-v3.sh H
  scripts/run-zworkforce-release-prompts-v3.sh RC
  GO_DECISION=GO AUTHORIZED_GO_BY=cvsz scripts/run-zworkforce-release-prompts-v3.sh I
  scripts/run-zworkforce-release-prompts-v3.sh all-pre-go
  scripts/run-zworkforce-release-prompts-v3.sh show <F|E|G|H|RC|I>
  scripts/run-zworkforce-release-prompts-v3.sh reset-stage <F|E|G|H|RC>

Required environment:
  NVIDIA_API_KEY=...

Optional:
  NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b
  NVIDIA_ENDPOINT=https://integrate.api.nvidia.com/v1/chat/completions
  REPO_DIR=/home/cvsz/zworkforce

Important:
  - Stage order is F -> E -> G -> H -> RC -> I.
  - Stage I never runs until F/E/G/H/RC have PASS markers.
  - The runner executes NVIDIA-requested bash commands itself.
  - Destructive and release-publication commands are blocked.
EOF
}

verify_repo() {
  need_cmd git

  [[ "$REPO_DIR" == "/home/cvsz/zworkforce" || "$REPO_DIR" == */zworkforce ]] || \
    die "REPO_DIR must point to lowercase zworkforce checkout: $REPO_DIR"

  [[ -d "$REPO_DIR/.git" ]] || die "REPO_DIR is not a Git repository: $REPO_DIR"

  local remote remote_lc
  remote="$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null || true)"
  remote_lc="$(printf '%s' "$remote" | tr '[:upper:]' '[:lower:]')"

  [[ "$remote_lc" == *"github.com/cvsz/zworkforce"* ]] || \
    die "origin does not look like cvsz/zworkforce: $remote"

  git -C "$REPO_DIR" fetch --quiet --prune origin main

  local checkout_sha checkout_branch main_sha
  checkout_sha="$(git -C "$REPO_DIR" rev-parse HEAD)"
  checkout_branch="$(git -C "$REPO_DIR" branch --show-current 2>/dev/null || true)"
  main_sha="$(git -C "$REPO_DIR" rev-parse refs/remotes/origin/main)"

  echo "Current checkout: ${checkout_branch:-DETACHED} @ $checkout_sha"
  echo "Verified origin/main: $main_sha"
  echo "Expected frozen candidate: $FROZEN_CANDIDATE"

  git -C "$REPO_DIR" cat-file -e "$FROZEN_CANDIDATE^{commit}" 2>/dev/null || \
    die "frozen candidate is not a commit object after fetch: $FROZEN_CANDIDATE"

  if [[ "$main_sha" != "$FROZEN_CANDIDATE" ]]; then
    if [[ "$ALLOW_CANDIDATE_DRIFT" != "1" ]]; then
      die "candidate drift: origin/main=$main_sha expected=$FROZEN_CANDIDATE"
    fi
    echo "WARNING: candidate drift explicitly allowed; SHA-bound evidence may need rerun." >&2
  fi

  if [[ "$checkout_sha" != "$main_sha" ]]; then
    echo "NOTE: checkout differs from origin/main; allowed for evidence/work branches." >&2
    echo "      Release candidate authority remains origin/main=$main_sha." >&2
  fi

  if [[ "$ALLOW_DIRTY_WORKTREE" != "1" && -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
    die "dirty worktree not allowed"
  fi
}

verify_nvidia() {
  need_cmd python3
  [[ -n "${NVIDIA_API_KEY:-}" ]] || die "NVIDIA_API_KEY is not set"
}

stage_marker() {
  echo "$STATE_DIR/$1.pass"
}

stage_is_passed() {
  [[ -f "$(stage_marker "$1")" ]]
}

show_status() {
  verify_repo
  echo
  echo "Evidence stage markers:"
  local s
  for s in F E G H RC; do
    if stage_is_passed "$s"; then
      echo "  $s: PASS ($(cat "$(stage_marker "$s")" 2>/dev/null || true))"
    else
      echo "  $s: NOT VERIFIED"
    fi
  done
  if [[ -f "$STATE_DIR/I.complete" ]]; then
    echo "  I: COMPLETE ($(cat "$STATE_DIR/I.complete"))"
  else
    echo "  I: NOT COMPLETE"
  fi
}

require_prior_stage() {
  local current="$1"
  case "$current" in
    F) ;;
    E) stage_is_passed F || die "Stage E blocked: F not PASS" ;;
    G)
      stage_is_passed F || die "Stage G blocked: F not PASS"
      stage_is_passed E || die "Stage G blocked: E not PASS"
      ;;
    H)
      stage_is_passed F || die "Stage H blocked: F not PASS"
      stage_is_passed E || die "Stage H blocked: E not PASS"
      stage_is_passed G || die "Stage H blocked: G not PASS"
      ;;
    RC)
      for s in F E G H; do
        stage_is_passed "$s" || die "RC blocked: $s not PASS"
      done
      ;;
    I)
      for s in F E G H RC; do
        stage_is_passed "$s" || die "Stage I blocked: $s not PASS"
      done
      ;;
    *) die "unknown stage: $current" ;;
  esac
}

expected_verdict_regex() {
  case "$1" in
    F)  echo '^STAGE F VERDICT:[[:space:]]*PASS[[:space:]]*$' ;;
    E)  echo '^STAGE E VERDICT:[[:space:]]*PASS[[:space:]]*$' ;;
    G)  echo '^STAGE G VERDICT:[[:space:]]*PASS[[:space:]]*$' ;;
    H)  echo '^STAGE H VERDICT:[[:space:]]*PASS[[:space:]]*$' ;;
    RC) echo '^IMMUTABLE RC VERDICT:[[:space:]]*PASS[[:space:]]*$' ;;
    I)  echo '^FINAL VERDICT:[[:space:]]*COMPLETE[[:space:]]*$' ;;
  esac
}

record_stage_pass_if_valid() {
  local stage="$1" log_file="$2" regex
  regex="$(expected_verdict_regex "$stage")"

  if ! grep -Eq "$regex" "$log_file"; then
    echo "No exact PASS verdict found for stage $stage; marker NOT recorded." >&2
    return 2
  fi

  if [[ "$stage" == "I" ]]; then
    printf '%s candidate=%s authorized_go_by=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "$FROZEN_CANDIDATE" \
      "${AUTHORIZED_GO_BY:-UNKNOWN}" > "$STATE_DIR/I.complete"
  else
    printf '%s candidate=%s log=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "$FROZEN_CANDIDATE" \
      "$log_file" > "$(stage_marker "$stage")"
  fi
}

common_header() {
  cat <<EOF
You are executing zWorkforce v3.0.3 external release evidence.

Repository:
$REPO_DIR

Canonical GitHub repository:
cvsz/zworkforce

Frozen candidate:
$FROZEN_CANDIDATE

Rules:
- Run all shell commands inside $REPO_DIR.
- Never use /home/user.
- Use bash tool calls for commands; do not merely describe commands.
- Do not print or expose secrets.
- Do not modify source unless a real P0/P1 release blocker is discovered.
- Do not tag or publish v3.0.3.
- Local/CI simulation does not substitute for mandatory external evidence.
EOF
}

prompt_F() {
  common_header
  cat <<'EOF'
STAGE F — STORAGE / VECTOR EXTERNAL EVIDENCE

Verify the actual current release configuration first.

For external S3-compatible artifact storage:
- use the supported configured backend;
- Supabase Storage S3 compatibility is acceptable if compatible with the existing adapter;
- verify upload, persistence, retrieval, SHA-256, byte length, MIME metadata;
- verify same-tenant read;
- prove cross-tenant denial;
- verify nonexistent/unauthorized access fails;
- verify size/malformed input policy;
- signed URL expiry if applicable;
- delete/lifecycle behavior;
- restart/reconnect/retrieve;
- ensure credentials are absent from logs/API/client output.

For vector backend:
- determine whether Qdrant is mandatory for v3.0.3;
- if mandatory, verify real external Qdrant index/search/reindex/delete and tenant isolation;
- if optional/disabled, record that accurately;
- never silently replace Qdrant with pgvector.

If every mandatory external Stage F requirement is verified, end exactly:
STAGE F VERDICT: PASS

Otherwise end exactly:
STAGE F VERDICT: PENDING EXTERNAL EVIDENCE
EOF
}

prompt_E() {
  common_header
  cat <<'EOF'
STAGE E — MULTI-REPLICA HA EXTERNAL EVIDENCE

Use real shared infrastructure with at least:
- 2 scheduler-eligible replicas;
- 2 workers;
- 2 outbox-eligible replicas where required;
- shared managed PostgreSQL.

Verify:
- exactly one scheduler lease holder;
- terminate leader and measure takeover;
- no duplicate scheduled execution;
- worker crash after claim then lease expiry/reclaim by another worker;
- no duplicate external side effect;
- outbox ownership failover;
- event delivery without duplicate;
- valid HMAC accepted;
- invalid HMAC denied;
- duplicate webhook deduped;
- bounded retry/backoff;
- dead-letter behavior;
- bounded DB/network interruption without split brain or silent loss.

Single-replica local compose is not sufficient.

If all mandatory Stage E requirements pass, end exactly:
STAGE E VERDICT: PASS

Otherwise:
STAGE E VERDICT: PENDING EXTERNAL EVIDENCE
EOF
}

prompt_G() {
  common_header
  cat <<'EOF'
STAGE G — OBSERVABILITY / ALERT EXTERNAL EVIDENCE

Verify deployed staging:
- /health and /ready;
- authenticated metrics;
- queue/task/worker/scheduler/outbox/dead-letter metrics;
- provider success/error/circuit/retry/fallback/latency metrics;
- real OTLP trace arrival;
- request -> task -> worker -> provider/tool correlation;
- structured log correlation;
- secrets absent from logs/traces;
- one bounded failure visible in result + logs + metrics + trace;
- one safe test alert delivered through the external alert router to the operator channel;
- record safe delivery timestamp/receipt ID.

Configuration without actual external delivery is not PASS.

If all mandatory Stage G requirements pass, end exactly:
STAGE G VERDICT: PASS

Otherwise:
STAGE G VERDICT: PENDING EXTERNAL EVIDENCE
EOF
}

prompt_H() {
  common_header
  cat <<'EOF'
STAGE H — TRUSTED WINDOWS SIGNING / LIVE HTTPS

Do not use CI's temporary/self-signed certificate as production proof.

Verify:
- exact release candidate;
- release Windows package;
- trusted code-signing identity;
- package identity/version/SHA-256/publisher;
- trusted signature and chain;
- timestamp where applicable;
- clean install;
- launch/process survival/relaunch;
- supported upgrade if applicable;
- uninstall/reinstall;
- live HTTPS endpoint;
- invalid TLS rejection;
- HTTP downgrade rejection where required;
- valid auth;
- invalid auth denial;
- tenant/role/scope;
- release-required task/agent/automation/approval flows;
- no provider secrets in package/logs/static config/UI.

If all mandatory Stage H requirements pass, end exactly:
STAGE H VERDICT: PASS

Otherwise:
STAGE H VERDICT: PENDING EXTERNAL EVIDENCE
EOF
}

prompt_RC() {
  common_header
  cat <<'EOF'
IMMUTABLE RC CLOSURE

Do not publish.

Verify exact frozen candidate and record:
- Git SHA and verification status;
- version;
- schema version/migration chain;
- exact candidate checks/reviews/threads;
- immutable OCI image digest;
- Python wheel filename + SHA-256;
- Python sdist filename + SHA-256;
- Windows package filename + SHA-256 + trusted signature status;
- SBOM + digest;
- provenance/attestation;
- exact rollback target including Git SHA, OCI digest, DB compatibility assumptions and rollback procedure.

A mutable tag alone is not a rollback plan.

If every immutable RC prerequisite is verified, end exactly:
IMMUTABLE RC VERDICT: PASS

Otherwise:
IMMUTABLE RC VERDICT: PENDING
EOF
}

prompt_I() {
  common_header
  cat <<EOF
STAGE I — TERMINAL GO / NO-GO

Requested GO identity:
${AUTHORIZED_GO_BY:-UNSET}

Independently re-check all underlying evidence; local marker files are not proof.

Require:
- exact candidate;
- zero P0;
- zero actionable unresolved P1;
- exact candidate CI/security/Windows checks green;
- required independent review;
- zero blocking review threads;
- A staging evidence;
- B managed PostgreSQL/PITR/RPO/RTO;
- C OIDC/JWKS/auth;
- D external provider/failover;
- E multi-replica HA;
- F storage/vector;
- G OTLP/metrics/alert delivery;
- H trusted Windows signing/live HTTPS;
- immutable OCI digest;
- SBOM/provenance;
- Python checksums;
- Windows checksum/signature;
- rollback target;
- security approval;
- release approval;
- explicit authorized GO.

If any mandatory item is absent, DO NOT tag or publish and end exactly:
FINAL VERDICT: REPOSITORY COMPLETE / EXTERNAL EVIDENCE PENDING

Only if every mandatory gate is verified may you end:
FINAL VERDICT: COMPLETE
EOF
}

show_prompt() {
  case "$1" in
    F) prompt_F ;;
    E) prompt_E ;;
    G) prompt_G ;;
    H) prompt_H ;;
    RC) prompt_RC ;;
    I) prompt_I ;;
    *) die "unknown stage: $1" ;;
  esac
}

run_nvidia_stage() {
  local stage="$1" prompt="$2" stamp log_dir log_file rc

  verify_repo
  require_prior_stage "$stage"
  verify_nvidia

  if [[ "$stage" == "I" ]]; then
    [[ "${GO_DECISION:-}" == "GO" ]] || die "Stage I requires GO_DECISION=GO"
    [[ -n "${AUTHORIZED_GO_BY:-}" ]] || die "Stage I requires AUTHORIZED_GO_BY"
  fi

  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  log_dir="$LOG_ROOT/$stamp"
  mkdir -p "$log_dir"
  log_file="$log_dir/stage-$stage.log"

  echo
  echo "============================================================"
  echo "Running zWorkforce release stage: $stage"
  echo "Frozen candidate: $FROZEN_CANDIDATE"
  echo "Repository: $REPO_DIR"
  echo "Agent: NVIDIA NIM"
  echo "NVIDIA model: $NVIDIA_MODEL"
  echo "NVIDIA endpoint: $NVIDIA_ENDPOINT"
  echo "Log: $log_file"
  echo "============================================================"

  set +e
  STAGE_PROMPT="$prompt" \
  STAGE_NAME="$stage" \
  REPO_DIR="$REPO_DIR" \
  NVIDIA_ENDPOINT="$NVIDIA_ENDPOINT" \
  NVIDIA_MODEL="$NVIDIA_MODEL" \
  NVIDIA_MAX_TOKENS="$NVIDIA_MAX_TOKENS" \
  NVIDIA_TEMPERATURE="$NVIDIA_TEMPERATURE" \
  NVIDIA_MAX_TOOL_ROUNDS="$NVIDIA_MAX_TOOL_ROUNDS" \
  COMMAND_TIMEOUT_SECONDS="$COMMAND_TIMEOUT_SECONDS" \
  python3 - <<'PY' 2>&1 | tee "$log_file"
import json, os, re, shlex, subprocess, sys, urllib.request, urllib.error

repo = os.environ["REPO_DIR"]
endpoint = os.environ["NVIDIA_ENDPOINT"]
model = os.environ["NVIDIA_MODEL"]
api_key = os.environ["NVIDIA_API_KEY"]
max_tokens = int(os.environ["NVIDIA_MAX_TOKENS"])
temperature = float(os.environ["NVIDIA_TEMPERATURE"])
max_rounds = int(os.environ["NVIDIA_MAX_TOOL_ROUNDS"])
timeout = int(os.environ["COMMAND_TIMEOUT_SECONDS"])
prompt = os.environ["STAGE_PROMPT"]
stage = os.environ["STAGE_NAME"]

# Commands that must never be autonomously executed by the evidence runner.
DENY_PATTERNS = [
    r'(^|\s)sudo(\s|$)',
    r'\brm\s+-rf\b',
    r'\bmkfs\b',
    r'\bdd\s+if=',
    r'\bshutdown\b',
    r'\breboot\b',
    r'\bpoweroff\b',
    r'\bgit\s+push\b',
    r'\bgit\s+tag\b',
    r'\bgh\s+release\s+create\b',
    r'\bdocker\s+system\s+prune\b',
    r'\bgit\s+reset\s+--hard\b',
    r'\bgit\s+clean\s+-[a-zA-Z]*f',
    r'\bcurl\b.*\|\s*(ba)?sh\b',
    r'\bwget\b.*\|\s*(ba)?sh\b',
]

def safe_command(cmd):
    c = cmd.strip()
    if not c:
        return False, "empty command"
    if "/home/user" in c:
        return False, "/home/user is forbidden"
    for pat in DENY_PATTERNS:
        if re.search(pat, c, re.I):
            return False, f"blocked by safety policy: {pat}"
    return True, ""

def run_bash(command):
    ok, reason = safe_command(command)
    if not ok:
        return {"exit_code": 126, "stdout": "", "stderr": reason}
    try:
        p = subprocess.run(
            ["bash", "-lc", command],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        # Bound tool output returned to model.
        stdout = p.stdout[-30000:]
        stderr = p.stderr[-15000:]
        return {"exit_code": p.returncode, "stdout": stdout, "stderr": stderr}
    except subprocess.TimeoutExpired as e:
        return {
            "exit_code": 124,
            "stdout": (e.stdout or "")[-10000:] if isinstance(e.stdout, str) else "",
            "stderr": f"command timed out after {timeout}s",
        }

tools = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Execute a bounded shell command inside /home/cvsz/zworkforce. "
            "Do not use sudo, destructive filesystem operations, git push/tag, "
            "or release publication commands."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            },
            "required": ["command"],
            "additionalProperties": False
        }
    }
}]

messages = [
    {
        "role": "system",
        "content": (
            "You are a release-evidence engineer. Use the bash tool to actually inspect "
            "and test the repository/environment. Never invent evidence. Never expose secrets. "
            "All commands run in /home/cvsz/zworkforce. Do not ask to use /home/user. "
            "Do not output pseudo tool-call JSON as plain text when a tool is available."
        )
    },
    {"role": "user", "content": prompt},
]

def call_nvidia(msgs):
    body = {
        "model": model,
        "messages": msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tools": tools,
        "tool_choice": "auto",
        "stream": False,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"NVIDIA HTTP {e.code}: {detail[:4000]}")

for round_idx in range(max_rounds):
    response = call_nvidia(messages)
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError(f"NVIDIA returned no choices: {response}")
    msg = choices[0].get("message") or {}
    content = msg.get("content") or ""
    tool_calls = msg.get("tool_calls") or []

    assistant_msg = {"role": "assistant", "content": content}
    if tool_calls:
        assistant_msg["tool_calls"] = tool_calls
    messages.append(assistant_msg)

    if tool_calls:
        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = fn.get("name")
            raw_args = fn.get("arguments") or "{}"
            if name != "bash":
                result = {"exit_code": 126, "stdout": "", "stderr": f"unsupported tool {name}"}
            else:
                try:
                    args = json.loads(raw_args)
                    command = args.get("command", "")
                except Exception as exc:
                    result = {"exit_code": 126, "stdout": "", "stderr": f"bad tool args: {exc}"}
                else:
                    print(f"$ {command}", flush=True)
                    result = run_bash(command)
                    if result["stdout"]:
                        print(result["stdout"], end="" if result["stdout"].endswith("\n") else "\n", flush=True)
                    if result["stderr"]:
                        print(result["stderr"], file=sys.stderr, flush=True)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", f"tool-{round_idx}"),
                "name": name or "bash",
                "content": json.dumps(result),
            })
        continue

    # Some models may emit a simple pseudo tool-call JSON despite tool support.
    # We accept exactly one JSON object only if it is structurally safe, execute it,
    # and feed the real result back. This prevents the false-positive behavior seen
    # previously while remaining fail-closed.
    stripped = content.strip()
    pseudo = None
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            if obj.get("tool") == "bash" and isinstance(obj.get("args"), dict):
                pseudo = obj
        except Exception:
            pass

    if pseudo:
        command = pseudo["args"].get("command", "")
        print(f"$ {command}", flush=True)
        result = run_bash(command)
        if result["stdout"]:
            print(result["stdout"], end="" if result["stdout"].endswith("\n") else "\n", flush=True)
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr, flush=True)
        messages.append({
            "role": "user",
            "content": (
                "The runner executed your requested bash command. Real result:\n"
                + json.dumps(result)
                + "\nContinue using the bash tool for any further commands."
            ),
        })
        continue

    # Final natural-language answer.
    print(content)
    sys.exit(0)

raise RuntimeError(f"NVIDIA exceeded max tool rounds ({max_rounds})")
PY
  rc="${PIPESTATUS[0]}"
  set -e

  [[ "$rc" -eq 0 ]] || die "stage $stage NVIDIA runner exited with code $rc"

  if grep -Fq '/home/user' "$log_file"; then
    die "stage $stage referenced /home/user; evidence invalid"
  fi

  if record_stage_pass_if_valid "$stage" "$log_file"; then
    echo "Stage $stage PASS marker recorded."
  else
    echo "Stage $stage completed but remains NOT VERIFIED." >&2
    echo "Review: $log_file" >&2
    return 2
  fi

  echo "Evidence log: $log_file"
}

reset_stage() {
  case "$1" in
    F|E|G|H|RC)
      rm -f "$(stage_marker "$1")"
      echo "Removed PASS marker for stage $1"
      ;;
    *) die "reset-stage accepts F|E|G|H|RC" ;;
  esac
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    verify|check)
      verify_repo
      verify_nvidia
      echo "Candidate verification PASS."
      echo "NVIDIA configuration present."
      ;;
    status)
      show_status
      ;;
    F)
      run_nvidia_stage F "$(prompt_F)"
      ;;
    E)
      run_nvidia_stage E "$(prompt_E)"
      ;;
    G)
      run_nvidia_stage G "$(prompt_G)"
      ;;
    H)
      run_nvidia_stage H "$(prompt_H)"
      ;;
    RC)
      run_nvidia_stage RC "$(prompt_RC)"
      ;;
    I)
      run_nvidia_stage I "$(prompt_I)"
      ;;
    all-pre-go)
      run_nvidia_stage F "$(prompt_F)"
      run_nvidia_stage E "$(prompt_E)"
      run_nvidia_stage G "$(prompt_G)"
      run_nvidia_stage H "$(prompt_H)"
      run_nvidia_stage RC "$(prompt_RC)"
      echo "Pre-GO sequence finished. Stage I was NOT executed."
      ;;
    show)
      [[ $# -eq 2 ]] || die "show requires stage"
      show_prompt "$2"
      ;;
    reset-stage)
      [[ $# -eq 2 ]] || die "reset-stage requires stage"
      reset_stage "$2"
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      usage
      die "unknown command: $cmd"
      ;;
  esac
}

main "$@"
