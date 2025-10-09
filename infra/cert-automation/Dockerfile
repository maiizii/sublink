FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        certbot \
        python3-certbot-dns-cloudflare \
        sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY fetch_domains.py ./fetch_domains.py
COPY deploy-hook.sh ./deploy-hook.sh
COPY entrypoint.sh ./entrypoint.sh

RUN chmod +x ./entrypoint.sh ./deploy-hook.sh

ENTRYPOINT ["/app/entrypoint.sh"]
