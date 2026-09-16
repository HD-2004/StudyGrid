# syntax=docker/dockerfile:1

FROM node:22-alpine AS web-build
WORKDIR /workspace/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.14-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    ENVIRONMENT=production \
    STUDYGRID_DB_PATH=/data/studygrid.db \
    PLAN_RETENTION_DAYS=30 \
    MATERIAL_MAX_UPLOAD_MB=25 \
    MATERIAL_MAX_TEXT_CHARS=60000
WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt

COPY app/ ./app/
COPY --from=web-build /workspace/web/dist ./web/dist/

RUN useradd --create-home --uid 10001 studygrid \
    && mkdir -p /data \
    && chown studygrid:studygrid /data
USER studygrid

VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=3)"

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
