FROM python:3.12-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates openssl libglib2.0-0 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrate.py ./migrate.py

RUN mkdir -p storage/snaps

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Railway injects $PORT — must listen on it, not hardcoded 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
