#!/usr/bin/env bash
set -Eeuo pipefail

image="${1:-zeaz/provider:0.4.0}"

configured_user="$(docker image inspect "$image" --format '{{.Config.User}}')"
if [[ "$configured_user" != "zeaz" ]]; then
  echo "container user is not zeaz" >&2
  exit 1
fi

docker run \
  --rm \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges:true \
  --tmpfs /tmp:size=64m,mode=1777 \
  --entrypoint /bin/sh \
  "$image" \
  -ceu '
    test "$(id -u)" -eq 10001
    root_options="$(awk "\$2 == \"/\" { print \$4 }" /proc/mounts)"
    case ",${root_options}," in
      *,ro,*) ;;
      *)
        echo "root mount is not read-only" >&2
        exit 1
        ;;
    esac
    if touch /app/config/providers.yaml 2>/dev/null; then
      echo "root filesystem unexpectedly writable" >&2
      exit 1
    fi
    touch /tmp/write-probe
    test "$(awk "/^CapEff:/ { print \$2 }" /proc/self/status)" = "0000000000000000"
    test "$(awk "/^NoNewPrivs:/ { print \$2 }" /proc/self/status)" = "1"
  '
