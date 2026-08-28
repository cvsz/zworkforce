FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_NAME=zcoder \
    APP_VERSION=1.33.0 \
    API_HOST=127.0.0.1 \
    API_PORT=8000 \
    REDIS_ENABLED=false \
    PROTOBUF_ENABLED=false \
    NATS_ENABLED=false \
    OTEL_ENABLED=false

RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /usr/sbin/nologin --create-home appuser

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-deploy.lock

COPY app/ ./app/
COPY src/ ./src/
COPY webapp/ ./webapp/
COPY AGENTS.md README.md litellm-config.yaml ./

RUN mkdir -p /app/data/uploads /app/logs /tmp/uploads && \
    chown -R appuser:appgroup /app /tmp/uploads

USER appuser

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/ready || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1"]
