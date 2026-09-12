FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir . \
    && mkdir -p /app/data \
    && chown -R app:app /app

USER app

EXPOSE 8218

CMD ["uvicorn", "ztrader_intel.api:app", "--host", "0.0.0.0", "--port", "8218"]
