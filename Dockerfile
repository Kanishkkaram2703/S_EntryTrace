# ============================================================
# S*EntryTrace — Dockerfile
# Multi-stage build: Node (frontend) + Python (backend) + nginx
# ============================================================

# ── Stage 1: Build Frontend ─────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Production Image ───────────────────────────────
FROM python:3.11-slim

LABEL maintainer="Kanishk Karam"
LABEL description="S*EntryTrace — Android Digital Forensics Workstation"
LABEL version="0.1.0"

# System dependencies required by MVT, cryptography, ADB, and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    android-tools-adb \
    nginx \
    libusb-1.0-0 \
    libjpeg62-turbo \
    zlib1g \
    libffi-dev \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install MVT from local source
# MVT uses setuptools-scm which requires .git — set version explicitly for Docker
COPY mvt-main/ ./mvt-main/
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_MVT=2.0.0
RUN pip install --no-cache-dir ./mvt-main

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend from Stage 1
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist

# Create data directories
RUN mkdir -p /app/evidence /app/reports /app/logs

# ── nginx config: serve frontend + reverse-proxy /api to backend ──
RUN cat > /etc/nginx/sites-available/default << 'NGINX'
server {
    listen 80;
    server_name _;

    # Serve static frontend
    root /app/frontend/dist;
    index index.html;

    # API reverse proxy to uvicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    # Frontend SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

# ── supervisord config: run nginx + uvicorn together ──
RUN cat > /etc/supervisor/conf.d/sentrytrace.conf << 'SUPERVISOR'
[supervisord]
nodaemon=true
logfile=/dev/null
logfile_maxbytes=0

[program:backend]
command=python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0

[program:nginx]
command=nginx -g "daemon off;"
autostart=true
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
stderr_logfile=/dev/fd/2
stderr_logfile_maxbytes=0
SUPERVISOR

# Environment variables with safe defaults
ENV STE_ENVIRONMENT=production
ENV STE_SAFE_MODE=true
ENV STE_ADB_PATH=/usr/bin/adb
ENV STE_EVIDENCE_DIR=/app/evidence
ENV STE_REPORTS_DIR=/app/reports
ENV STE_LOG_DIR=/app/logs
ENV PYTHONUNBUFFERED=1

# Expose HTTP port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

# Start both services via supervisor
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
