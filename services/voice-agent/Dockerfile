FROM python:3.12-slim-bookworm

ARG SPEECH_TO_SPEECH_VERSION=0.2.11
ARG QWENTTS_CPP_VERSION=0.3.1+cpu
ARG QWENTTS_WHEEL_INDEX=https://huggingface.co/datasets/andito/qwentts-cpp-python-wheels/tree/main/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models/huggingface \
    TRANSFORMERS_CACHE=/models/huggingface/transformers \
    XDG_CACHE_HOME=/models/cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl ffmpeg libgomp1 libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir \
       "qwentts-cpp-python==${QWENTTS_CPP_VERSION}" \
       --find-links "${QWENTTS_WHEEL_INDEX}" \
    && python -m pip install --no-cache-dir \
       "speech-to-speech[faster-whisper]==${SPEECH_TO_SPEECH_VERSION}"

RUN groupadd --system zplatform \
    && useradd --system --gid zplatform --home-dir /app --create-home zplatform \
    && mkdir -p /models/huggingface /models/cache \
    && chown -R zplatform:zplatform /app /models

WORKDIR /app
COPY entrypoint.sh healthcheck.py /app/
RUN chmod 0555 /app/entrypoint.sh /app/healthcheck.py

USER zplatform

EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=12 CMD ["python", "/app/healthcheck.py"]
ENTRYPOINT ["/app/entrypoint.sh"]
