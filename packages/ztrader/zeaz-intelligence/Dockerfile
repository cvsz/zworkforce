FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8218

CMD ["uvicorn", "ztrader_intel.api:app", "--host", "0.0.0.0", "--port", "8218"]
