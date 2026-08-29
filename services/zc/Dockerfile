FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY services/zc/requirements-enterprise.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/zc/app ./app
COPY services/zc/src ./src
COPY services/zc/webapp ./webapp

RUN addgroup --system --gid 10001 zc \
    && adduser --system --uid 10001 --ingroup zc zc \
    && mkdir -p /data/uploads /data/logs \
    && chown -R zc:zc /app /data

USER zc

EXPOSE 8420 8421

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/v1/wire/health/live').read()"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8420", "--workers", "2"]
