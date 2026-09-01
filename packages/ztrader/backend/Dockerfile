# // ZeaZDev [Backend Dockerfile Production Build] //
# // Project: ztrader Platform //
# // Version: 1.0.0 (Unified Scaffolding) //
# // Author: ZeaZDev Meta-Intelligence //
# // --- DO NOT EDIT HEADER --- //

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src:/app/src/ztrader/abt

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

EXPOSE 8000
USER appuser
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "ztrader.main:app", "--host", "0.0.0.0", "--port", "8000"]
