FROM python:3.14-slim AS runtime
ARG VERSION=3.0.3
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
LABEL org.opencontainers.image.title="zWorkforce" \
      org.opencontainers.image.description="Enterprise AI Workforce Operating System" \
      org.opencontainers.image.source="https://github.com/cvsz/zWorkforce" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"
COPY pyproject.toml README.md LICENSE ./
COPY zworkforce ./zworkforce
RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir ".[s3]" \
    && groupadd --system --gid 10001 zworkforce \
    && useradd --system --uid 10001 --gid zworkforce --home /nonexistent --shell /usr/sbin/nologin zworkforce \
    && mkdir -p /data /workspace /artifacts \
    && chown -R zworkforce:zworkforce /data /workspace /artifacts /app
USER 10001:10001
ENV ZWORKFORCE_DATA_DIR=/data ZWORKFORCE_WORKSPACE_ROOT=/workspace ZWORKFORCE_ARTIFACT_DIR=/artifacts ZWORKFORCE_HOST=0.0.0.0 ZWORKFORCE_PORT=9569
EXPOSE 9569
VOLUME ["/data", "/workspace", "/artifacts"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["python","-c","import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:9569/health',timeout=3))['status']=='ok'"]
ENTRYPOINT ["zworkforce"]
CMD ["serve"]
