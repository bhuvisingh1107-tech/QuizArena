#!/bin/sh
set -e

PORT="${PORT:-8000}"

echo "Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "Starting QuizArena API on 0.0.0.0:${PORT} (proxy headers enabled for Render)..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips='*'
