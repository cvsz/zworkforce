FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY app ./app
COPY assets ./assets
COPY docs ./docs
COPY web ./web
COPY database_schema.sql ./database_schema.sql

RUN useradd --create-home --uid 10001 uperfect \
    && mkdir -p /data \
    && chown -R uperfect:uperfect /app /data

USER uperfect

EXPOSE 18765

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18765"]
