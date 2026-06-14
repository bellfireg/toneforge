# ToneForge backend — FastAPI + faster-whisper + parselmouth + edge-tts
FROM python:3.12-slim

# System deps: ffmpeg (whisper audio decode), curl (healthcheck)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application code
COPY backend ./backend
COPY app ./app

# Runtime config (overridable via compose / -e):
#   edge-tts lives on PATH in the image; DB persists to a mounted volume
ENV EDGE_TTS_BIN=edge-tts \
    DB_PATH=/data/tutor.db \
    PYTHONUNBUFFERED=1

# faster-whisper "small" model downloads on first run into this cache
ENV HF_HOME=/data/hf-cache

EXPOSE 8900

# Whisper model loads at startup — give it a generous start period
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://localhost:8900/health || exit 1

WORKDIR /app/backend
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8900"]
