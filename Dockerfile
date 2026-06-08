FROM python:3.14-slim

# Niebuforowane logi (od razu widoczne w `docker logs`).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODE=web \
    DATA_DIR=/data \
    WEB_PORT=8080

WORKDIR /app

# Zaciągnij łatki bezpieczeństwa pakietów bazowych Debiana.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Aktualne pip/setuptools/wheel (usuwa CVE w samym pip) + zależności aplikacji.
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

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
