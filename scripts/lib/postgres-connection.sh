#!/usr/bin/env bash

# Configure libpq through a short-lived, mode-0600 service file. Keeping the
# DSN out of pg_dump/pg_restore arguments prevents credentials from appearing
# in process listings or diagnostic output.

postgres_configure_service() {
  local service_file dsn rest authority userinfo hostdb hostport dbquery query
  local user password host port dbname sslmode connect_timeout

  dsn="${1:-${ZWORKFORCE_DATABASE_URL:-}}"
  [[ -n "$dsn" ]] || {
    echo "a PostgreSQL connection URL is required" >&2
    return 2
  }
  case "$dsn" in
    postgres://*|postgresql://*) ;;
    *)
      echo "ZWORKFORCE_DATABASE_URL must use the postgres or postgresql scheme" >&2
      return 2
      ;;
  esac

  rest="${dsn#*://}"
  authority="${rest%%/*}"
  hostdb="${rest#*/}"
  [[ "$authority" == *@* && "$hostdb" != "$rest" ]] || {
    echo "ZWORKFORCE_DATABASE_URL must include credentials, host, and database" >&2
    return 2
  }
  userinfo="${authority%@*}"
  hostport="${authority##*@}"
  user="${userinfo%%:*}"
  password="${userinfo#*:}"
  [[ "$userinfo" == *:* ]] || password=""

  if [[ "$hostport" == \[*\]:* ]]; then
    host="${hostport#\[}"
    host="${host%\]*}"
    port="${hostport##*:}"
  else
    host="${hostport%%:*}"
    port="${hostport##*:}"
    [[ "$hostport" == *:* ]] || port="5432"
  fi
  dbquery="${hostdb%%\?*}"
  query=""
  [[ "$hostdb" == *\?* ]] && query="${hostdb#*\?}"
  dbname="$dbquery"
  [[ -n "$host" && -n "$port" && "$port" =~ ^[0-9]+$ && -n "$dbname" ]] || {
    echo "ZWORKFORCE_DATABASE_URL has an invalid host, port, or database" >&2
    return 2
  }

  # Decode URI components before writing the libpq service file. Raw backslashes
  # and malformed percent escapes are rejected so printf cannot reinterpret
  # credential data as a format string or control sequence.
  user="$(postgres_url_decode "$user")" || return 2
  password="$(postgres_url_decode "$password")" || return 2
  host="$(postgres_url_decode "$host")" || return 2
  dbname="$(postgres_url_decode "$dbname")" || return 2
  sslmode="prefer"
  connect_timeout=""
  if [[ -n "$query" ]]; then
    local pair key value
    local -a query_pairs
    IFS='&' read -r -a query_pairs <<< "$query"
    for pair in "${query_pairs[@]}"; do
      key="${pair%%=*}"
      value="${pair#*=}"
      [[ "$pair" == *=* ]] || continue
      case "$key" in
        sslmode) sslmode="$(postgres_url_decode "$value")" || return 2 ;;
        connect_timeout) connect_timeout="$(postgres_url_decode "$value")" || return 2 ;;
      esac
    done
  fi

  service_file="$(mktemp "${TMPDIR:-/tmp}/zworkforce-pg-service.XXXXXX")"
  chmod 600 "$service_file"
  {
    printf '[zworkforce]\n'
    printf 'host=%s\nport=%s\nuser=%s\npassword=%s\ndbname=%s\nsslmode=%s\n' \
      "$host" "$port" "$user" "$password" "$dbname" "$sslmode"
    [[ -n "$connect_timeout" ]] && printf 'connect_timeout=%s\n' "$connect_timeout"
  } > "$service_file"

  export PGSERVICEFILE="$service_file"
  export PGSERVICE=zworkforce
  export ZWORKFORCE_PG_SERVICE_FILE="$service_file"
  unset ZWORKFORCE_DATABASE_URL
}

postgres_url_decode() {
  local input="$1" output="" prefix hex suffix character decoded
  case "$input" in
    *$'\n'*|*$'\r'*|*\\*)
    echo "ZWORKFORCE_DATABASE_URL contains an invalid control character" >&2
    return 1
    ;;
  esac
  while [[ "$input" =~ ^([^%]*)%([0-9A-Fa-f]{2})(.*)$ ]]; do
    prefix="${BASH_REMATCH[1]}"
    hex="${BASH_REMATCH[2]}"
    suffix="${BASH_REMATCH[3]}"
    [[ "$hex" != 00 ]] || {
      echo "ZWORKFORCE_DATABASE_URL contains a NUL escape" >&2
      return 1
    }
    printf -v character '%b' "\\x$hex"
    output+="$prefix$character"
    input="$suffix"
  done
  [[ "$input" != *%* ]] || {
    echo "ZWORKFORCE_DATABASE_URL contains a malformed percent escape" >&2
    return 1
  }
  decoded="${output}${input}"
  case "$decoded" in
    *$'\n'*|*$'\r'*|*\\*)
      echo "ZWORKFORCE_DATABASE_URL contains an invalid control character" >&2
      return 1
      ;;
  esac
  printf '%s' "$decoded"
}

postgres_cleanup_service() {
  if [[ -n "${ZWORKFORCE_PG_SERVICE_FILE:-}" ]]; then
    rm -f -- "$ZWORKFORCE_PG_SERVICE_FILE"
  fi
  unset PGSERVICEFILE PGSERVICE ZWORKFORCE_PG_SERVICE_FILE
}
