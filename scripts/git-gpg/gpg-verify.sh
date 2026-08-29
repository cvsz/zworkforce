#!/usr/bin/env bash
set -euo pipefail
REF="${1:-HEAD}"
MODE="${2:-commits}"
verify_commits() {
    local ref="$1" count="${2:-10}"
    echo "🔍 Verifying last $count commits on $ref..."
    echo "─────────────────────────────────────────────"
    git log "$ref" -"$count" --format="%h %G? %an  %s" | while read -r line; do
        status=$(echo "$line" | awk '{print $2}')
        case "$status" in G) icon="✅" ;; B) icon="⚠️ " ;; N) icon="⏭️ " ;; *) icon="❌" ;; esac
        echo " $icon  $line"
    done
}
verify_tags() {
    echo "🔍 Verifying all tags..."
    echo "─────────────────────────────────────────────"
    git tag -l | while read -r tag; do
        verify=$(git verify-tag --raw "$tag" 2>&1 || true)
        if echo "$verify" | grep -q "VALIDSIG"; then echo " ✅  $tag"
        else echo " ❌  $tag  (unsigned or invalid)"; fi
    done
}
case "$MODE" in
    commits) verify_commits "$REF" ;;
    tags)    verify_tags ;;
    all)     verify_commits "$REF"; echo ""; verify_tags ;;
    *)       echo "Usage: $0 [ref] [commits|tags|all]"; exit 1 ;;
esac
