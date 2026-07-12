# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the React SPA into app/webui
# ---------------------------------------------------------------------------
FROM node:26-slim AS webui
WORKDIR /build
# Install deps first for better layer caching.
COPY frontend/package.json frontend/package-lock.json* ./frontend/
# Use `npm ci` for reproducible installs straight from the committed lockfile.
RUN cd frontend && npm ci
# Build the SPA. vite.config.ts emits to ../app/webui (i.e. /build/app/webui).
COPY frontend ./frontend
RUN cd frontend && npm run build

# ---------------------------------------------------------------------------
# Stage 2 — Python runtime that serves the SPA + JSON API
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WPUPDATER_DATA_DIR=/data \
    WPUPDATER_PORT=8090

WORKDIR /app

# tini for clean signal handling; tzdata so the scheduler honours TZ.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini tzdata ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY wsgi.py .
# Drop in the SPA built in stage 1 (overwrites any stale local build).
COPY --from=webui /build/app/webui ./app/webui

RUN mkdir -p /data && useradd -m -u 10001 wpupdater && chown -R wpupdater /data /app
USER wpupdater

EXPOSE 8090
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8090/healthz || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
# A single worker keeps one in-process scheduler thread, which is what we want;
# 8 threads handle concurrent dashboard/API requests.
CMD ["gunicorn", "--bind", "0.0.0.0:8090", "--workers", "1", "--threads", "8", \
     "--timeout", "300", "wsgi:app"]

