# Deployment

Guide for running QuizArena with Docker Compose and nginx.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- A domain name (production) and TLS certificates (recommended)

## File layout

```
QuizArena/
├── docker-compose.yml          # Dev-ish stack (db + backend + frontend)
├── docker-compose.prod.yml     # Production stack (+ edge nginx)
├── backend/Dockerfile
├── frontend/Dockerfile
└── nginx/
    ├── nginx.conf
    ├── conf.d/quizarena.conf
    └── proxy_params.conf
```

## Development compose

```bash
cp .env.example .env
cp backend/.env.example backend/.env

docker compose up --build
```

| Service | Port | Notes |
|---------|------|-------|
| PostgreSQL | 5432 | Persistent volume `postgres_data` |
| Backend | 8000 | Runs `alembic upgrade head` on start |
| Frontend | 8080 | Built with direct backend URLs for browser access |

Seed the admin account after first boot:

```bash
docker compose exec backend python -m scripts.seed_admin
```

## Production compose

1. Copy and edit environment files:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

2. Set required values in `.env`:

- `POSTGRES_PASSWORD` — strong database password

3. Set required values in `backend/.env`:

- `APP_ENV=production`
- `DEBUG=false`
- `JWT_SECRET_KEY` — long random secret
- `PUBLIC_APP_URL=https://your-domain.example`
- `CORS_ORIGINS=https://your-domain.example`
- `TRUSTED_HOSTS=your-domain.example`

4. Start the stack:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

5. Seed admin (once):

```bash
docker compose -f docker-compose.prod.yml exec backend python -m scripts.seed_admin
```

### Production URL routing

Edge nginx terminates HTTP (and HTTPS when configured):

| Path | Upstream |
|------|----------|
| `/` | frontend (SPA) |
| `/api/*` | backend:8000 |
| `/ws` | backend:8000 (WebSocket upgrade) |

The frontend production build uses same-origin defaults (`VITE_API_BASE_URL=/api/v1`, empty `VITE_WS_BASE_URL`).

## HTTPS

1. Place certificates in `nginx/ssl/` (e.g. Let's Encrypt `fullchain.pem` + `privkey.pem`).
2. Uncomment the `listen 443 ssl` block and certificate paths in `nginx/conf.d/quizarena.conf`.
3. Uncomment the HTTPS port mapping in `docker-compose.prod.yml`.
4. Enable the HTTP → HTTPS redirect in `quizarena.conf`.

## Health checks

| Service | Check |
|---------|-------|
| Backend | `GET /api/v1/live` |
| Frontend | HTTP 200 on `/` |
| PostgreSQL | `pg_isready` |
| nginx | HTTP 200 on `/` |

Kubernetes / load balancers should use `/api/v1/ready` for readiness (includes DB check).

## Migrations

Migrations run automatically via `backend/scripts/entrypoint.sh` on container start.

Verify manually:

```bash
docker compose exec backend python scripts/verify_migrations.py
```

## Scaling notes

- **Single instance** is the default; WebSocket state is in-process.
- For horizontal scaling, introduce a shared pub/sub layer for WebSocket fan-out (not included in v1).
- Use nginx rate limit zones for login/join; tune `LOGIN_RATE_LIMIT_PER_MINUTE` and `JOIN_RATE_LIMIT_PER_MINUTE` in backend env.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 502 on `/api` | Backend logs: `docker compose logs backend` |
| WebSocket disconnects | nginx `proxy_read_timeout` (default 3600s in prod config) |
| CORS errors | `CORS_ORIGINS` must match browser origin exactly |
| Migration failures | DB connectivity, `DATABASE_URL`, Alembic revision history |

See [Backups.md](./Backups.md) for database backup and rollback procedures.
