#!/bin/sh
set -e

PORT="${PORT:-8000}"
cd /app

echo "Alembic script location: /app/alembic/versions"
ls -la /app/alembic/versions

HOST_MIGRATION="/app/alembic/versions/20260802_2000_host_accounts.py"
if [ ! -f "$HOST_MIGRATION" ]; then
  echo "ERROR: Required migration missing from image: $HOST_MIGRATION" >&2
  echo "The Neon alembic_version table may already reference 20260802_2000_host_accounts." >&2
  echo "Redeploy GitHub main (commit that includes Login System) with a cleared Docker build cache." >&2
  exit 1
fi

echo "Running database migrations (alembic upgrade head)..."
alembic -c /app/alembic.ini current || true
alembic -c /app/alembic.ini heads
alembic -c /app/alembic.ini upgrade head
alembic -c /app/alembic.ini current

echo "Starting QuizArena API on 0.0.0.0:${PORT} (proxy headers enabled for Render)..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips='*'
