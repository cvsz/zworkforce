#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

file="${1:-.env.cloudflare}"
[[ -f "$file" ]] || exit 0

tmp="$(mktemp "${file}.clean.XXXXXX")"
chmod 600 "$tmp"

python3 - "$file" > "$tmp" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
assign_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

output: list[str | None] = []
key_to_index: dict[str, int] = {}
optional_empty_drop = {
    "CLOUDFLARE_AUDIT_TOKEN",
    "CLOUDFLARE_AI_GATEWAY_TOKEN",
}
# .env.cloudflare is generated scoped-token output. These keys belong in .env
# only. Keeping them in .env.cloudflare makes manual `source .env.cloudflare`
# able to override a valid bootstrap token with a generated/expired token.
protected_generated_env_drop = {
    "CLOUDFLARE_BOOTSTRAP_TOKEN",
}

def normalize_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value

for line in lines:
    match = assign_re.match(line)
    if not match:
        output.append(line)
        continue

    key, raw_value = match.group(1), match.group(2)
    value = normalize_value(raw_value)

    if key in protected_generated_env_drop and path.name == ".env.cloudflare":
        if key in key_to_index:
            output[key_to_index[key]] = None
            key_to_index.pop(key, None)
        continue

    if key in optional_empty_drop and value == "":
        if key in key_to_index:
            output[key_to_index[key]] = None
            key_to_index.pop(key, None)
        continue

    normalized = f"{key}={value}"

    if key in key_to_index:
        output[key_to_index[key]] = normalized
    else:
        key_to_index[key] = len(output)
        output.append(normalized)

for line in output:
    if line is not None:
        print(line)
PY

mv "$tmp" "$file"
chmod 600 "$file"
