FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS builder
WORKDIR /build
COPY requirements-build.lock requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-build.lock && \
    pip wheel --no-cache-dir --require-hashes --wheel-dir /wheels -r requirements.lock
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-cache-dir --no-build-isolation --no-deps --wheel-dir /wheels .

FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ZEAZ_CONFIG=/app/config/providers.yaml \
    ZEAZ_HOST=0.0.0.0
RUN groupadd --gid 10001 zeaz && \
    useradd --uid 10001 --gid zeaz --shell /usr/sbin/nologin --no-create-home zeaz
COPY --from=builder /wheels /wheels
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
      --require-hashes -r /tmp/requirements.lock && \
    pip install --no-cache-dir --no-index --find-links=/wheels \
      --no-deps zeaz-provider==0.4.0rc1 && \
    rm -rf /wheels /tmp/requirements.lock
WORKDIR /app
COPY --chown=zeaz:zeaz config/providers.example.yaml /app/config/providers.yaml
USER zeaz
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=3)"]
ENTRYPOINT ["zeaz-provider"]
