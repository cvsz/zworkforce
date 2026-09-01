# Docker

Run zRouter in a container. Published image: [`decolua/zrouter`](https://hub.docker.com/r/decolua/zrouter) — multi-platform `linux/amd64` + `linux/arm64`.

---

# For Users

## Quick start

```bash
docker run -d \
  -p 20128:20128 \
  -v "$HOME/.zrouter:/app/data" \
  -e DATA_DIR=/app/data \
  --name zrouter \
  decolua/zrouter:latest
```

App listens on port `20128`. Open: http://localhost:20128

For production, also set:
- `NEXT_PUBLIC_BASE_URL=https://your-domain.com`
- `JWT_SECRET` (random 64-char hex)
- `INITIAL_PASSWORD` (strong password)
- `API_KEY_SECRET`
- `MACHINE_ID_SALT`

The container adds enterprise security headers automatically (HSTS, X-Frame-Options DENY, Permissions-Policy) in production mode.

## Manage container

```bash
docker logs -f zrouter        # view logs
docker stop zrouter           # stop
docker start zrouter          # start again
docker rm -f zrouter          # remove
```

## Health check

The image includes a built-in HEALTHCHECK that probes port 20128 every 30s:

```bash
docker inspect --format='{{.State.Health.Status}}' zrouter
```

## Data persistence

```bash
-v "$HOME/.zrouter:/app/data" \
-e DATA_DIR=/app/data
```

Without `DATA_DIR`, the app falls back to `~/.zrouter/` (macOS/Linux) or `%APPDATA%\zrouter\` (Windows). In the container, `DATA_DIR=/app/data` makes the bind mount work.

Data layout under `$DATA_DIR/`:

```text
$DATA_DIR/
├── db/
│   ├── data.sqlite       # main SQLite database
│   └── backups/          # auto backups
└── ...                   # certs, logs, runtime configs
```

Host path: `$HOME/.zrouter/db/data.sqlite`
Container path: `/app/data/db/data.sqlite`

## Optional env vars

```bash
docker run -d \
  -p 20128:20128 \
  -v "$HOME/.zrouter:/app/data" \
  -e DATA_DIR=/app/data \
  -e PORT=20128 \
  -e HOSTNAME=0.0.0.0 \
  -e DEBUG=true \
  --name zrouter \
  decolua/zrouter:latest
```

## Optional Headroom sidecar

The zRouter image does not bundle Python or Headroom. To use Headroom in Docker, run it as a separate service and point zRouter at that proxy:

```yaml
services:
  zrouter:
    image: decolua/zrouter:latest
    ports:
      - "20128:20128"
    volumes:
      - "$HOME/.zrouter:/app/data"
    environment:
      DATA_DIR: /app/data
      HEADROOM_URL: http://headroom:8787
    depends_on:
      - headroom

  headroom:
    image: ghcr.io/chopratejas/headroom:latest
    ports:
      - "8787:8787"
```

In the dashboard, open `Endpoint` → `Token Saver` → `Headroom`, confirm the URL is `http://headroom:8787`, recheck status, then enable Headroom.

If Headroom runs on the Docker host instead of as a sidecar, use `http://host.docker.internal:8787` on macOS/Windows. On Linux, add `--add-host=host.docker.internal:host-gateway` or the equivalent compose `extra_hosts` entry.

## Production deployment (Cloudflare Tunnel)

For public deployment behind Cloudflare Tunnel, use the provided compose stack:

```bash
docker compose -f docker-compose.public.yml up -d
```

This starts:
- `zrouter` (app, healthy on port 20128)
- `caddy` (reverse proxy, ports 80/443)

The tunnel provides HTTPS with auto-provisioned certificates. See `deploy-public.sh` for the full automated deployment script.

## Update to latest

```bash
docker pull decolua/zrouter:latest
docker rm -f zrouter
# re-run the quick start command
```

---

# For Developers

## Build image locally (test)

```bash
cd app && docker build -t zrouter .

docker run --rm -p 20128:20128 \
  -v "$HOME/.zrouter:/app/data" \
  -e DATA_DIR=/app/data \
  zrouter
```

## Publish (automatic via CI)

Push a git tag `v*` → GitHub Actions builds multi-platform (amd64+arm64) and pushes to:
- `ghcr.io/decolua/zrouter:v{version}` + `:latest`
- `decolua/zrouter:v{version}` + `:latest`

```bash
# Use scripts/release.js (recommended)
node scripts/release.js "Release title" "Notes"

# Or manually
git tag v0.6.0 && git push origin v0.6.0
```

Workflow: `app/.github/workflows/docker-publish.yml`
