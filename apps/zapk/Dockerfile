FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --system --uid 10001 --create-home appuser
COPY app ./app
RUN mkdir -p /srv/data && chown -R 10001:10001 /srv/data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/zapk/api/health',timeout=2)"
CMD ["uvicorn","app.main:root_app","--host","0.0.0.0","--port","8000","--no-proxy-headers"]
