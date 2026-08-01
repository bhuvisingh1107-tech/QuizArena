# Environment Variables

Configuration reference for QuizArena. Copy `backend/.env.example` → `backend/.env` and root `.env.example` → `.env` for Docker Compose.

## Application

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | `development`, `production`, or `test` |
| `DEBUG` | `false` | Enable OpenAPI docs and verbose errors |
| `LOG_LEVEL` | `INFO` | Python log level |
| `LOG_FORMAT` | `json` | `json` or `text` |
| `PUBLIC_APP_URL` | `http://localhost:5173` | Public SPA URL for join/display links |

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./quizarena.db` | SQLAlchemy connection string |
| `DB_POOL_SIZE` | `5` | Connection pool size (PostgreSQL) |
| `DB_MAX_OVERFLOW` | `10` | Extra connections beyond pool size |

Production requires PostgreSQL (`postgresql://user:pass@host:5432/dbname`).

## Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | `change-me-in-production` | HMAC secret for admin JWT |
| `JWT_EXPIRY_HOURS` | `8` | Admin token lifetime |
| `ADMIN_USERNAME` | `admin` | Seed script username |
| `ADMIN_PASSWORD` | — | Plaintext password for seed (preferred locally) |
| `ADMIN_PASSWORD_HASH` | — | Pre-computed bcrypt hash alternative |

## Network / security

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `TRUSTED_HOSTS` | `*` | Comma-separated hosts for TrustedHostMiddleware |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | In-app login rate limit per IP |
| `JOIN_RATE_LIMIT_PER_MINUTE` | `30` | In-app join rate limit per IP |

## Upload limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_BYTES` | `15728640` (15 MiB) | Max single media upload |
| `MAX_REQUEST_BODY_BYTES` | `20971520` (20 MiB) | Max JSON body size |

## Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_BACKEND` | `local` | `local` or `cloud` (cloud not implemented in v1) |
| `STORAGE_PATH` | `../storage` | Local filesystem path for uploads |

## Frontend (Vite)

| Variable | Default (unset) | Description |
|----------|-----------------|-------------|
| `VITE_API_BASE_URL` | `/api/v1` | REST API prefix |
| `VITE_WS_BASE_URL` | `ws(s)://<host>/ws` | WebSocket base URL |

Set explicitly for direct backend access without a proxy:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_BASE_URL=ws://localhost:8000/ws
```

## Docker Compose (root `.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `quizarena` | PostgreSQL user |
| `POSTGRES_PASSWORD` | — | **Required in production** |
| `POSTGRES_DB` | `quizarena` | Database name |
| `POSTGRES_PORT` | `5432` | Host port (dev compose) |
| `BACKEND_PORT` | `8000` | Host port (dev compose) |
| `FRONTEND_PORT` | `8080` | Host port (dev compose) |
| `HTTP_PORT` | `80` | Edge nginx port (prod compose) |

## Production checklist

- [ ] `APP_ENV=production`
- [ ] `DEBUG=false`
- [ ] Strong `JWT_SECRET_KEY`
- [ ] PostgreSQL `DATABASE_URL`
- [ ] `PUBLIC_APP_URL` and `CORS_ORIGINS` match your domain
- [ ] `TRUSTED_HOSTS` set to your domain (not `*`)
- [ ] `POSTGRES_PASSWORD` set in root `.env`

See [Deployment.md](./Deployment.md) for operational details.
