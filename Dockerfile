FROM python:3.12-bookworm

WORKDIR /app

# OpenCV headless needs these runtime libs in slim/bookworm images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        openssl \
        ffmpeg \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        libgl1 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -c "import cv2; assert hasattr(cv2, 'CascadeClassifier'), cv2.__file__"

COPY app ./app
COPY migrate.py ./migrate.py

RUN mkdir -p storage/snaps storage/recordings

ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV OPENCV_LOG_LEVEL=ERROR

EXPOSE 8000

# Railway injects $PORT — must listen on it, not hardcoded 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
