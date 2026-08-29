#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Lossless API-key normalizer and validator.
#
# The organize command NEVER removes lines, comments, blank lines, duplicate
# assignments, or unsupported variables. It only normalizes assignments whose
# names match *_*_KEY:
#
#   OPENAI_API_KEY='value'  -> OPENAI_API_KEY="value"
#   OPENAI_API_KEY="value"  -> OPENAI_API_KEY="value"
#   OPENAI_API_KEY=value    -> OPENAI_API_KEY="value"
#
# Existing outer single/double quotes are removed first. The raw value is then
# escaped and enclosed in one pair of double quotes.
#
# Usage:
#   APIKEY_FILE=.apikey ./scripts/apikey-manager.sh organize
#   APIKEY_FILE=.apikey ./scripts/apikey-manager.sh lint
#   APIKEY_FILE=.apikey ./scripts/apikey-manager.sh test
#   APIKEY_FILE=.apikey ./scripts/apikey-manager.sh report
#   APIKEY_FILE=.apikey ./scripts/apikey-manager.sh all

readonly APIKEY_FILE="${APIKEY_FILE:-.apikey}"
readonly APIKEY_REPORT="${APIKEY_REPORT:-apikey-validation-report.csv}"
readonly APIKEY_TIMEOUT="${APIKEY_TIMEOUT:-15}"
readonly APIKEY_CONNECT_TIMEOUT="${APIKEY_CONNECT_TIMEOUT:-5}"
readonly COMMAND="${1:-all}"

readonly NORMALIZE_NAME_RE='^[A-Z][A-Z0-9_]*_[A-Z0-9]+_KEY$'
readonly PARSE_NAME_RE='^[A-Z][A-Z0-9_]*(API_KEY|SECRET_KEY)$'
readonly PLACEHOLDER_RE='^$|^\.+$|^[xX*]+$|^replace([-_ ]?me)?$|^your([-_ ]?.*)?$|^change([-_ ]?me)?$|^todo$|^tbd$|^null$|^none$|^undefined$|^example$|^dummy$|^test$|^secret$|^api[-_ ]?key$'

declare -Ar TEST_URLS=(
  [CEREBRAS_API_KEY]="https://api.cerebras.ai/v1/models"
  [CODESTRAL_API_KEY]="https://codestral.mistral.ai/v1/models"
  [DASHSCOPE_API_KEY]="https://dashscope.aliyuncs.com/compatible-mode/v1/models"
  [DEEPSEEK_API_KEY]="https://api.deepseek.com/models"
  [FIREWORKS_API_KEY]="https://api.fireworks.ai/inference/v1/models"
  [GEMINI_API_KEY]="https://generativelanguage.googleapis.com/v1beta/models"
  [GROQ_API_KEY]="https://api.groq.com/openai/v1/models"
  [MISTRAL_API_KEY]="https://api.mistral.ai/v1/models"
  [NVIDIA_NIM_API_KEY]="https://integrate.api.nvidia.com/v1/models"
  [OPENAI_API_KEY]="https://api.openai.com/v1/models"
  [OPENROUTER_API_KEY]="https://openrouter.ai/api/v1/models"
  [SAMBANOVA_API_KEY]="https://api.sambanova.ai/v1/models"
)

declare -Ar TEST_METHODS=(
  [GEMINI_API_KEY]="query"
)

tmp_paths=()

cleanup() {
  local path
  for path in "${tmp_paths[@]:-}"; do
    [[ -n "$path" ]] && rm -rf -- "$path"
  done
  return 0
}
trap cleanup EXIT

log() { printf '%s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

make_tmp() {
  local path
  path="$(mktemp)"
  chmod 600 "$path"
  tmp_paths+=("$path")
  printf '%s' "$path"
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

strip_outer_quotes() {
  local value="$1"

  while :; do
    if (( ${#value} >= 2 )) &&
       [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
      value="${value:1:${#value}-2}"
      continue
    fi

    if (( ${#value} >= 2 )) &&
       [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
      continue
    fi

    break
  done

  printf '%s' "$value"
}

escape_double_quoted_env() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\r'/}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

mask() {
  local value="$1"
  if (( ${#value} <= 8 )); then
    printf '********'
  else
    printf '%s…%s' "${value:0:4}" "${value: -4}"
  fi
}

is_placeholder() {
  local value="${1,,}"
  [[ "$value" =~ $PLACEHOLDER_RE ]]
}

require_tools() {
  local tool
  for tool in awk chmod cp curl date grep install mktemp sed; do
    command -v "$tool" >/dev/null 2>&1 || die "Missing command: $tool"
  done
}

ensure_file() {
  [[ -f "$APIKEY_FILE" ]] || die "Credential file not found: $APIKEY_FILE"
  [[ -r "$APIKEY_FILE" ]] || die "Credential file is not readable: $APIKEY_FILE"
  chmod 600 "$APIKEY_FILE"
}

normalize_line() {
  local original="$1"
  local working="$original"
  local prefix=""
  local name
  local raw
  local value

  if [[ "$working" =~ ^([[:space:]]*)export[[:space:]]+ ]]; then
    prefix="${BASH_REMATCH[1]}export "
    working="${working:${#BASH_REMATCH[0]}}"
  elif [[ "$working" =~ ^([[:space:]]*) ]]; then
    prefix="${BASH_REMATCH[1]}"
    working="${working:${#BASH_REMATCH[1]}}"
  fi

  [[ "$working" == *=* ]] || {
    printf '%s' "$original"
    return 0
  }

  name="$(trim "${working%%=*}")"

  [[ "$name" =~ $NORMALIZE_NAME_RE ]] || {
    printf '%s' "$original"
    return 0
  }

  raw="${working#*=}"
  value="$(trim "$raw")"
  value="$(strip_outer_quotes "$value")"

  printf '%s%s="%s"' "$prefix" "$name" "$(escape_double_quoted_env "$value")"
}

organize() {
  local output
  local backup
  local stamp
  local line

  output="$(make_tmp)"
  stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
  backup="${APIKEY_FILE}.backup.${stamp}"

  cp -- "$APIKEY_FILE" "$backup"
  chmod 600 "$backup"

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    normalize_line "$line"
    printf '\n'
  done < "$APIKEY_FILE" > "$output"

  install -m 600 "$output" "$APIKEY_FILE"

  log "Normalized without deleting lines: $APIKEY_FILE"
  log "Backup: $backup"
}

read_entries() {
  local line
  local working
  local name
  local raw
  local value
  local line_no=0

  while IFS= read -r line || [[ -n "$line" ]]; do
    ((line_no += 1))
    line="${line%$'\r'}"
    working="$(trim "$line")"

    [[ -z "$working" || "$working" == \#* ]] && continue

    if [[ "$working" == export[[:space:]]* ]]; then
      working="$(trim "${working#export}")"
    fi

    if [[ "$working" != *=* ]]; then
      printf 'IGNORED\t%s\t%s\n' "$line_no" "$line"
      continue
    fi

    name="$(trim "${working%%=*}")"
    raw="${working#*=}"
    value="$(strip_outer_quotes "$(trim "$raw")")"

    if [[ ! "$name" =~ $PARSE_NAME_RE ]]; then
      printf 'IGNORED_NAME\t%s\t%s\n' "$line_no" "$name"
      continue
    fi

    printf 'ENTRY\t%s\t%s\t%s\n' "$line_no" "$name" "$value"
  done < "$APIKEY_FILE"
}

lint() {
  local parsed
  local seen
  local status=0
  local kind line_no name value

  parsed="$(make_tmp)"
  seen="$(make_tmp)"
  read_entries > "$parsed"

  while IFS=$'\t' read -r kind line_no name value; do
    case "$kind" in
      ENTRY)
        if grep -Fxq "$name" "$seen"; then
          printf 'DUPLICATE    %-36s line %s\n' "$name" "$line_no"
          status=1
        else
          printf '%s\n' "$name" >> "$seen"
        fi

        if is_placeholder "$value"; then
          printf 'NOT_SET      %-36s\n' "$name"
          status=1
        elif (( ${#value} < 8 )) || [[ "$value" =~ [[:space:]] ]]; then
          printf 'SUSPICIOUS   %-36s %s\n' "$name" "$(mask "$value")"
          status=1
        else
          printf 'CONFIGURED   %-36s %s\n' "$name" "$(mask "$value")"
        fi
        ;;
      IGNORED|IGNORED_NAME)
        ;;
    esac
  done < "$parsed"

  return "$status"
}

classify_http() {
  case "$1" in
    200|201|202|204) printf VALID ;;
    401|403) printf INVALID ;;
    429) printf RATE_LIMITED ;;
    404) printf ENDPOINT_NOT_FOUND ;;
    500|502|503|504) printf PROVIDER_UNAVAILABLE ;;
    000|'') printf UNREACHABLE ;;
    *) printf UNKNOWN ;;
  esac
}

validate_one() {
  local name="$1"
  local value="$2"
  local url="$3"
  local method="${TEST_METHODS[$name]:-bearer}"
  local body
  local headers
  local code
  local rc=0
  local status

  body="$(make_tmp)"
  headers="$(make_tmp)"

  local -a args=(
    --silent
    --show-error
    --location
    --connect-timeout "$APIKEY_CONNECT_TIMEOUT"
    --max-time "$APIKEY_TIMEOUT"
    --output "$body"
    --dump-header "$headers"
    --write-out '%{http_code}'
    --header 'Accept: application/json'
    --header 'User-Agent: z-platform-apikey-validator/1.1'
  )

  case "$method" in
    bearer) args+=(--header "Authorization: Bearer ${value}") ;;
    query) args+=(--get --data-urlencode "key=${value}") ;;
  esac

  set +e
  code="$(curl "${args[@]}" "$url")"
  rc=$?
  set -e

  if (( rc != 0 )); then
    case "$rc" in
      5|6) status=DNS_ERROR ;;
      7) status=CONNECTION_FAILED ;;
      28) status=TIMEOUT ;;
      35|51|58|60|66|77|80|82|83|90|91) status=TLS_ERROR ;;
      *) status="NETWORK_ERROR_${rc}" ;;
    esac
    printf '%s\t%s\t000\tcurl_exit=%s\n' "$name" "$status" "$rc"
    return 2
  fi

  status="$(classify_http "$code")"
  printf '%s\t%s\t%s\tread-only validation endpoint\n' "$name" "$status" "$code"

  [[ "$status" == VALID || "$status" == RATE_LIMITED ]] && return 0
  [[ "$status" == INVALID ]] && return 1
  return 2
}

test_tsv() {
  local parsed
  local kind
  local name
  local value

  parsed="$(make_tmp)"
  read_entries > "$parsed"

  while IFS=$'\t' read -r kind _line_no name value; do
    [[ "$kind" == ENTRY ]] || continue

    if is_placeholder "$value"; then
      printf '%s\tNOT_CONFIGURED\t\tempty or placeholder value\n' "$name"
    elif [[ -n "${TEST_URLS[$name]:-}" ]]; then
      validate_one "$name" "$value" "${TEST_URLS[$name]}" || true
    else
      printf '%s\tUNTESTED\t\tno safe read-only validation endpoint configured\n' "$name"
    fi
  done < "$parsed"
}

test_keys() {
  local result
  local name
  local status
  local code
  local detail
  local rc=0

  result="$(make_tmp)"
  test_tsv > "$result"

  while IFS=$'\t' read -r name status code detail; do
    printf '%-22s %-36s HTTP %s\n' "$status" "$name" "${code:--}"
    [[ "$status" == INVALID ]] && rc=1

    case "$status" in
      DNS_ERROR|CONNECTION_FAILED|TIMEOUT|TLS_ERROR|UNREACHABLE|NETWORK_ERROR_*|UNKNOWN|ENDPOINT_NOT_FOUND|PROVIDER_UNAVAILABLE)
        [[ "$rc" -eq 0 ]] && rc=2
        ;;
    esac
  done < "$result"

  return "$rc"
}

csv_escape() {
  local value="${1//\"/\"\"}"
  printf '"%s"' "$value"
}

write_report() {
  local result
  local generated
  local dir
  local name status code detail

  result="$(make_tmp)"
  test_tsv > "$result"
  generated="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  dir="${APIKEY_REPORT%/*}"
  [[ "$dir" != "$APIKEY_REPORT" ]] && mkdir -p "$dir"

  {
    printf 'generated_at,name,status,http_status,detail\n'
    while IFS=$'\t' read -r name status code detail; do
      csv_escape "$generated"; printf ','
      csv_escape "$name"; printf ','
      csv_escape "$status"; printf ','
      csv_escape "$code"; printf ','
      csv_escape "$detail"; printf '\n'
    done < "$result"
  } > "$APIKEY_REPORT"

  chmod 600 "$APIKEY_REPORT"
  log "Report: $APIKEY_REPORT"
}

usage() {
  cat <<EOF
Usage: ${0##*/} {organize|lint|test|report|all|help}

organize:
  Preserves every line and normalizes only *_*_KEY assignments to NAME="VALUE".
  Existing outer single/double quotes are removed before adding double quotes.

Environment:
  APIKEY_FILE
  APIKEY_REPORT
  APIKEY_TIMEOUT
  APIKEY_CONNECT_TIMEOUT
EOF
}

main() {
  require_tools

  case "$COMMAND" in
    help|-h|--help) usage ;;
    organize) ensure_file; organize ;;
    lint) ensure_file; lint ;;
    test) ensure_file; test_keys ;;
    report) ensure_file; write_report ;;
    all)
      ensure_file
      organize
      printf '\n== Lint ==\n'
      lint || true
      printf '\n== Validation ==\n'
      test_keys || true
      printf '\n== Report ==\n'
      write_report
      ;;
    *)
      usage >&2
      die "Unknown command: $COMMAND"
      ;;
  esac
}

main "$@"
