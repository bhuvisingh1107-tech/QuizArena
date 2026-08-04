# Environment Variables

Configuration reference for QuizArena. Copy `backend/.env.example` → `backend/.env` and root `.env.example` → `.env` for Docker Compose.

## Application

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | `development`, `production`, or `test` |
| `DEBUG` | `false` | Enable OpenAPI docs and verbose errors |
| `LOG_LEVEL` | `INFO` | Python log level |
| `LOG_FORMAT` | `json` | `json` or `text` |
| `PUBLIC_APP_URL` | `http://localhost:5173` | Fallback SPA origin for API `joinUrl`/`displayUrl` when the request has no `Origin` header. Browser hosts rebuild links from `window.location.origin` (see `frontend/src/lib/app-url.ts`). |

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./quizarena.db` | SQLAlchemy connection string |
| `DB_POOL_SIZE` | `5` | Connection pool size (PostgreSQL) |
| `DB_MAX_OVERFLOW` | `10` | Extra connections beyond pool size |

Production requires PostgreSQL (`postgresql://user:pass@host:5432/dbname` or Neon with `?sslmode=require`).
`postgres://` URLs (common from Neon/Heroku) are auto-normalized to `postgresql://`.

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
| `CORS_ORIGINS` | `http://localhost:5173,...` | Exact allowed Origins (production SPA + localhost). No `*` in production. |
| `CORS_ORIGIN_REGEX` | HTTPS `*.vercel.app` | Extra Origins via `re.fullmatch` (Vercel production + previews). Empty disables. |
| `TRUSTED_HOSTS` | `*` | Comma-separated hosts for TrustedHostMiddleware (Render hostname in prod) |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | In-app login rate limit per IP |
| `JOIN_RATE_LIMIT_PER_MINUTE` | `30` | In-app join rate limit per IP |

## Upload limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_BYTES` | `15728640` (15 MiB) | Max single media upload |
| `MAX_REQUEST_BODY_BYTES` | `20971520` (20 MiB) | Max JSON body size |

## AI quiz generation

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `mock` | `openai` \| `openrouter` \| `gemini` \| `anthropic` \| `ollama` \| `openai_compatible`. `mock` is **tests only**. Required outside `APP_ENV=test` (startup fails if missing/invalid). |
| `AI_API_KEY` | empty | Required for all providers except `ollama` |
| `AI_API_BASE_URL` | provider preset | Override OpenAI-compatible base (optional for named aliases) |
| `AI_CHAT_MODEL` | provider default | Chat model id |
| `AI_EMBEDDING_MODEL` | provider default | Embedding model id (`local` = hash vectors; Anthropic always local) |
| `AI_MAX_SOURCE_BYTES` | `52428800` (50 MiB) | Max AI source file size |
| `AI_ENABLE_TOPIC_WEB` | `true` | Seed trusted educational URLs for topic mode |

### Provider presets

| `AI_PROVIDER` | Default base | Default chat model | Notes |
|---------------|--------------|--------------------|-------|
| `openai` | `https://api.openai.com/v1` | `gpt-4.1-mini` | **Production default** (embeddings: `text-embedding-3-small`) |
| `openrouter` | `https://openrouter.ai/api/v1` | `openai/gpt-4.1-mini` | OpenAI-compatible + Referer headers |
| `gemini` | Google AI Studio (optional) | `gemini-3.6-flash` | Alternate provider if `AI_PROVIDER=gemini` |
| `anthropic` | `https://api.anthropic.com` | `claude-3-5-haiku-latest` | Native Messages API; local embeddings |
| `ollama` | `http://127.0.0.1:11434/v1` | `llama3.2` | Local/dev; API key optional |
| `openai_compatible` | `https://api.openai.com/v1` | `gpt-4.1-mini` | Any OpenAI-compatible gateway |

See [AI_QUIZ_GENERATION.md](./AI_QUIZ_GENERATION.md) for architecture and optional extractors.

## Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_BACKEND` | `local` | `local` or `cloud` (cloud not implemented in v1) |
| `STORAGE_PATH` | `../storage` | Local filesystem path for uploads (`/app/storage` on Render disk) |

## Frontend (Vite / Vercel)

| Variable | Default (unset) | Description |
|----------|-----------------|-------------|
| `VITE_API_BASE_URL` | `/api/v1` | REST API prefix — on Vercel set to `https://<render>/api/v1` |
| `VITE_WS_BASE_URL` | `ws(s)://<host>/ws` | WebSocket URL — on Vercel set to `wss://<render>/ws` |
| `VITE_PUBLIC_APP_URL` | *(unset)* | Optional SPA origin override for join/display links. Leave unset so production uses `window.location.origin`. |

Local direct backend (no proxy):

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_BASE_URL=ws://localhost:8000/ws
```

Vercel production **and** preview (build-time — enable both environments):

```env
VITE_API_BASE_URL=https://quizarena-api.onrender.com/api/v1
VITE_WS_BASE_URL=wss://quizarena-api.onrender.com/ws
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

## Production checklist (Render + Vercel)

- [ ] Neon `DATABASE_URL` with `sslmode=require`
- [ ] `APP_ENV=production` and `DEBUG=false`
- [ ] Strong `JWT_SECRET_KEY`
- [ ] `PUBLIC_APP_URL` = Vercel origin
- [ ] `CORS_ORIGINS` = production Vercel origin (exact match)
- [ ] `CORS_ORIGIN_REGEX` allows HTTPS `*.vercel.app` (default) or empty if unused
- [ ] `TRUSTED_HOSTS` = Render hostname
- [ ] Vercel `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` set for **Production and Preview**
- [ ] `AI_PROVIDER` + `AI_API_KEY` set on Render (startup fails without them)
- [ ] Render persistent disk mounted at `/app/storage`
- [ ] Admin seeded once via `python -m scripts.seed_admin`

See [DEPLOY_RENDER_VERCEL.md](./DEPLOY_RENDER_VERCEL.md) for the full cloud guide and [Deployment.md](./Deployment.md) for Docker Compose.
