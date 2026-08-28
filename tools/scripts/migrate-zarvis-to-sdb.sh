#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$HOME/z-platform"
TARGET="/mnt/qwen-gen-data/zarvis"
ACTION_DIR="$TARGET/action"
PROACTIVE_DIR="$TARGET/proactive"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$TARGET/backups/migration-$STAMP"

cd "$ROOT"

mountpoint -q /mnt/qwen-gen-data || {
  echo "ERROR: /mnt/qwen-gen-data is not mounted"
  exit 1
}

mkdir -p "$ACTION_DIR" "$PROACTIVE_DIR" "$BACKUP_DIR"
chmod 750 "$TARGET" "$ACTION_DIR" "$PROACTIVE_DIR" "$TARGET/backups"

COMPOSE=(
  docker compose
  --env-file .env.zarvis.local
  -f compose.zarvis-local.yml
)

echo "[1/8] Stopping Z.A.R.V.I.S."
"${COMPOSE[@]}" down

ACTION_SOURCE="$(
  docker volume inspect \
    --format '{{.Mountpoint}}' \
    zarvis_action_data
)"

PROACTIVE_SOURCE="$(
  docker volume inspect \
    --format '{{.Mountpoint}}' \
    zarvis_proactive_data
)"

echo "[2/8] Creating verified backup"
sudo tar -C "$ACTION_SOURCE" \
  -czf "$BACKUP_DIR/zarvis_action_data.tar.gz" .

sudo tar -C "$PROACTIVE_SOURCE" \
  -czf "$BACKUP_DIR/zarvis_proactive_data.tar.gz" .

sudo chown -R "$(id -u):$(id -g)" "$BACKUP_DIR"

(
  cd "$BACKUP_DIR"
  sha256sum \
    zarvis_action_data.tar.gz \
    zarvis_proactive_data.tar.gz \
    > SHA256SUMS
  sha256sum -c SHA256SUMS
)

echo "[3/8] Copying durable data to /dev/sdb"
sudo find "$ACTION_DIR" \
  -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

sudo find "$PROACTIVE_DIR" \
  -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

sudo cp -a "$ACTION_SOURCE"/. "$ACTION_DIR"/
sudo cp -a "$PROACTIVE_SOURCE"/. "$PROACTIVE_DIR"/
sync

echo "[4/8] Replacing Docker volumes with bind-backed volumes"
docker volume rm \
  zarvis_action_data \
  zarvis_proactive_data

docker volume create \
  --driver local \
  --opt type=none \
  --opt o=bind \
  --opt device="$ACTION_DIR" \
  zarvis_action_data >/dev/null

docker volume create \
  --driver local \
  --opt type=none \
  --opt o=bind \
  --opt device="$PROACTIVE_DIR" \
  zarvis_proactive_data >/dev/null

echo "[5/8] Starting Z.A.R.V.I.S."
"${COMPOSE[@]}" up -d

echo "[6/8] Waiting for health"
for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8098/healthz >/dev/null &&
     curl -fsS http://127.0.0.1:8099/healthz >/dev/null
  then
    break
  fi

  if [[ "$attempt" -eq 60 ]]; then
    echo "ERROR: Health verification timed out"
    exit 1
  fi

  sleep 2
done

echo "[7/8] Verifying volume devices"
docker volume inspect \
  zarvis_action_data \
  zarvis_proactive_data \
  --format '{{.Name}} -> {{json .Options}}'

echo "[8/8] Final storage usage"
sudo du -sh "$ACTION_DIR" "$PROACTIVE_DIR"
df -hT /mnt/qwen-gen-data

echo
echo "Z.A.R.V.I.S. STORAGE MIGRATION: PASS"
echo "Backup: $BACKUP_DIR"
