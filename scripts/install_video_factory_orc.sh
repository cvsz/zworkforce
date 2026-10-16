#!/usr/bin/env bash
set -Eeuo pipefail

# Opt-in user-local installer. No root, service changes, tokens or external downloads.
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
INSTALL_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/zeaz-video-factory"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null || { echo 'Python 3 required' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 12)' || { echo 'Python >=3.12 required' >&2; exit 1; }
command -v ffprobe >/dev/null || { echo 'ffprobe required' >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo 'ffmpeg required' >&2; exit 1; }
SOURCE="$PROJECT_ROOT/scripts/video_factory_orc.py"
test -f "$SOURCE" || { echo 'Runtime missing' >&2; exit 1; }

if [[ "$DRY_RUN" == "1" ]]; then
  printf 'DRY RUN install: %s -> %s/runtime.py\n' "$SOURCE" "$INSTALL_HOME"
  printf 'DRY RUN launcher: %s/zeaz-video-factory\n' "$BIN_HOME"
  exit 0
fi
umask 077
mkdir -p "$INSTALL_HOME" "$BIN_HOME"
install -m 0600 "$SOURCE" "$INSTALL_HOME/runtime.py"
LAUNCHER="$BIN_HOME/zeaz-video-factory"
if [[ -e "$LAUNCHER" && ! -f "$LAUNCHER" ]]; then
  echo "Refusing non-regular launcher: $LAUNCHER" >&2
  exit 1
fi
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 "$INSTALL_HOME/runtime.py" "\$@"
EOF
chmod 0700 "$LAUNCHER"
printf 'Installed %s\n' "$LAUNCHER"
printf 'Run: %s --help\n' "$LAUNCHER"
printf 'No service started; no paid provider enabled; no deployment changed.\n'
