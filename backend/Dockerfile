FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the repository root (Render + docker compose).
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY backend/ ./

RUN addgroup --system quizarena \
    && adduser --system --ingroup quizarena --home /app quizarena \
    && mkdir -p /app/storage \
    && chmod +x /app/scripts/entrypoint.sh \
    && chown -R quizarena:quizarena /app

USER quizarena

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/live || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
