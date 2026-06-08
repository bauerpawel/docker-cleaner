FROM python:3.12-slim

# Niebuforowane logi (od razu widoczne w `docker logs`).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODE=web \
    DATA_DIR=/data \
    WEB_PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
        sys.exit(0) if os.environ.get('MODE','web').lower()=='console' else \
        urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('WEB_PORT','8080')+'/healthz', timeout=3)" \
    || exit 1

ENTRYPOINT ["python", "-m", "app.main"]
