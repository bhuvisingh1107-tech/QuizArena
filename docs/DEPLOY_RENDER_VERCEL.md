# Deploy QuizArena: Neon + Render + Vercel

Recommended production topology:

| Layer | Platform | Role |
|-------|----------|------|
| Database | [Neon](https://neon.tech) | Managed PostgreSQL |
| Backend API + WebSockets | [Render](https://render.com) | Docker web service |
| Frontend SPA | [Vercel](https://vercel.com) | Vite/React static hosting |

```
Browser ──HTTPS──► Vercel (SPA)
                │
                ├── REST ──HTTPS──► Render (/api/v1/*)
                └── WS   ──WSS────► Render (/ws)
Render ──SSL──► Neon PostgreSQL
```

> **Important:** Use a **paid / always-on** Render plan (Starter or higher). Free instances sleep and drop WebSocket connections.

---

## 1. PostgreSQL on Neon

### Create project

1. Create a Neon project (region close to your Render region, e.g. US West ≈ Oregon).
2. Create a database (default `neondb` is fine) or rename to `quizarena`.
3. Open **Connection details** → copy the connection string.

### Prefer the direct (non-pooler) URL

QuizArena uses a long-lived SQLAlchemy pool on Render. Use Neon’s **direct** connection host (not the `-pooler` host) unless you know you need PgBouncer.

Example (normalize `postgres://` → `postgresql://` is automatic in the app):

```text
postgresql://USER:PASSWORD@ep-xxxx.us-west-2.aws.neon.tech/neondb?sslmode=require
```

### Apply migrations

Migrations run **automatically** when the Render container starts (`alembic upgrade head` in `backend/scripts/entrypoint.sh`).

Manual verification (Render Shell or local with `DATABASE_URL` set):

```bash
cd backend
alembic upgrade head
python scripts/verify_migrations.py
```

### Neon checklist

- [ ] `sslmode=require` present on the URL
- [ ] Direct host (non-pooler) for Render
- [ ] Connection string saved for Render `DATABASE_URL`

See also [EnvironmentVariables.md](./EnvironmentVariables.md).

---

## 2. Backend on Render

### Option A — Blueprint (`render.yaml`)

1. Push this repo to GitHub/GitLab.
2. Render Dashboard → **New** → **Blueprint**.
3. Select the repo. Render reads [`render.yaml`](../render.yaml).
4. Fill sync-false env vars (see table below).
5. Deploy. Confirm health: `https://<service>.onrender.com/api/v1/ready`.

### Option B — Manual Docker web service

1. **New Web Service** → connect repo.
2. Runtime: **Docker**.
3. Dockerfile path: `./backend/Dockerfile`
4. Docker build context: repository root (`.`)
5. Health check path: `/api/v1/ready`
6. Attach a **persistent disk** at `/app/storage` (media uploads).
7. Set environment variables (table below).

### Seed the admin (once)

Render Shell for the service:

```bash
python -m scripts.seed_admin
```

Requires `ADMIN_USERNAME` + `ADMIN_PASSWORD` (or `ADMIN_PASSWORD_HASH`) in the environment.

### WebSockets on Render

- Endpoint: `wss://<service>.onrender.com/ws`
- Entrypoint enables `--proxy-headers` and `--forwarded-allow-ips=*` for Render’s TLS proxy.
- Native FastAPI WebSockets; no Socket.IO adapter required.
- Keep a single instance in v1 (in-memory room fan-out).

### Backend health endpoints

| Path | Use |
|------|-----|
| `GET /api/v1/live` | Liveness |
| `GET /api/v1/ready` | Readiness (DB) — use for Render health checks |
| `GET /api/v1/health` | Full status + WebSocket counts |

---

## 3. Frontend on Vercel

1. **New Project** → import the same repo.
2. **Root Directory:** `frontend`
3. Framework: Vite (auto-detected).
4. Build command: `npm run build`
5. Output directory: `dist`
6. Ensure [`frontend/vercel.json`](../frontend/vercel.json) is used (SPA refresh rewrites).
7. Set **Production and Preview** environment variables (build-time — both required):

   | Variable | Example |
   |----------|---------|
   | `VITE_API_BASE_URL` | `https://quizarena-api.onrender.com/api/v1` |
   | `VITE_WS_BASE_URL` | `wss://quizarena-api.onrender.com/ws` |

   In Vercel → Settings → Environment Variables, enable each for **Production** and **Preview**.
   Preview builds without these bake in relative `/api/v1` and login fails with "Network Error".

8. Deploy. Note the production URL, e.g. `https://quizarena.vercel.app`.

9. **Update Render** so join/display links and CORS match Vercel:

| Render env | Value |
|------------|-------|
| `PUBLIC_APP_URL` | `https://quizarena.vercel.app` |
| `CORS_ORIGINS` | `https://quizarena.vercel.app` |
| `CORS_ORIGIN_REGEX` | `https://([a-zA-Z0-9-]+\.)*vercel\.app` (default if unset) |
| `TRUSTED_HOSTS` | `quizarena-api.onrender.com` |

10. Redeploy backend after CORS/`PUBLIC_APP_URL` changes.

**Preview deployments:** Backend `CORS_ORIGIN_REGEX` allows HTTPS `*.vercel.app` with
`allow_credentials=True` (reflects the request Origin; never `*`). Keep the canonical
production origin in `CORS_ORIGINS`. Do not list each preview URL manually.

Copy [`frontend/.env.production.example`](../frontend/.env.production.example) as a template.

---

## Environment variables (complete list)

### Backend (Render)

| Variable | Required | Example / notes |
|----------|----------|-----------------|
| `APP_ENV` | Yes | `production` |
| `DEBUG` | Yes | `false` |
| `DATABASE_URL` | Yes | Neon `postgresql://…?sslmode=require` |
| `JWT_SECRET_KEY` | Yes | Long random secret (Render can generate) |
| `PUBLIC_APP_URL` | Yes | Vercel SPA origin (no trailing slash) |
| `CORS_ORIGINS` | Yes | Exact production SPA origin(s), comma-separated — no `*` |
| `CORS_ORIGIN_REGEX` | No | Default `https://([a-zA-Z0-9-]+\.)*vercel\.app` for preview hosts; empty disables |
| `TRUSTED_HOSTS` | Yes | Render hostname, e.g. `quizarena-api.onrender.com` |
| `ADMIN_USERNAME` | Seed | `admin` |
| `ADMIN_PASSWORD` | Seed once | Strong password (≥8 chars, mixed) |
| `ADMIN_PASSWORD_HASH` | Alt seed | bcrypt hash instead of plaintext |
| `JWT_EXPIRY_HOURS` | No | `8` |
| `LOG_LEVEL` | No | `INFO` |
| `LOG_FORMAT` | No | `json` |
| `DB_POOL_SIZE` | No | `5` |
| `DB_MAX_OVERFLOW` | No | `10` |
| `STORAGE_BACKEND` | No | `local` |
| `STORAGE_PATH` | No | `/app/storage` (persistent disk) |
| `MAX_UPLOAD_BYTES` | No | `15728640` |
| `MAX_REQUEST_BODY_BYTES` | No | `20971520` |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | No | `10` |
| `JOIN_RATE_LIMIT_PER_MINUTE` | No | `30` |
| `AI_PROVIDER` | Yes | `openai` (production default) — or `openrouter` / `gemini` / `anthropic` / `openai_compatible` / `ollama`. Startup fails if unset/`mock` |
| `AI_API_KEY` | Yes* | Provider API key (*optional only for `ollama`) |
| `AI_API_BASE_URL` | No | Override preset base URL |
| `AI_CHAT_MODEL` | No | Production: `gpt-4.1-mini` (OpenAI). Examples: `openai/gpt-4.1-mini`, `gemini-3.6-flash` |
| `AI_EMBEDDING_MODEL` | No | Production: `text-embedding-3-small` |
| `PORT` | Auto | Set by Render |

### Frontend (Vercel — build time)

| Variable | Required | Example |
|----------|----------|---------|
| `VITE_API_BASE_URL` | Yes | `https://<render-host>/api/v1` |
| `VITE_WS_BASE_URL` | Yes | `wss://<render-host>/ws` |

### Neon

Provided inside `DATABASE_URL` only (no separate app vars).

---

## Post-deploy verification checklist

Work through each item on production URLs:

| # | Check | How |
|---|--------|-----|
| 1 | API ready | `curl -sf https://<render>/api/v1/ready` |
| 2 | Admin login | Vercel `/admin/login` with seeded credentials |
| 3 | Quiz Builder | Create quiz → sections → questions → media → publish |
| 4 | Live Room | Create room → open lobby → copy join + display URLs |
| 5 | QR Join | Scan/open QR → participant join page with room code |
| 6 | Participant App | Join → lobby → answer → reveal → leaderboard → results |
| 7 | Presenter Display | Open display URL on a second screen; no answer buttons; state sync |
| 8 | WebSockets | Browser Network → WS `wss://…/ws` connected; pause/resume updates all clients |
| 9 | Results | End session → admin results + CSV export |

### Common failures

| Symptom | Fix |
|---------|-----|
| CORS blocked | `CORS_ORIGINS` must match the production origin; previews need `CORS_ORIGIN_REGEX` (HTTPS `*.vercel.app`) |
| Preview Network Error | Set `VITE_API_*` for Preview on Vercel, then redeploy; confirm Render CORS regex |
| WS fails / 404 | Confirm `VITE_WS_BASE_URL=wss://…/ws` and Render plan is always-on |
| 400 Bad Host | Add Render hostname to `TRUSTED_HOSTS` |
| Join/display wrong domain | Host UI rebuilds links from `window.location.origin` via `getAppOrigin()` — redeploy the Vercel frontend. Optionally set Render `PUBLIC_APP_URL` for API-returned URLs when no Origin header is present. |
| DB connection error | Neon URL + `sslmode=require`; use direct host |
| Media 404 after restart | Attach Render persistent disk at `/app/storage` |
| SPA refresh 404 | Confirm `frontend/vercel.json` rewrites and Root Directory=`frontend` |

---

## Migrations reference

| When | What runs |
|------|-----------|
| Every Render deploy / restart | `alembic upgrade head` via entrypoint |
| Manual | `alembic upgrade head` |
| Verify | `python scripts/verify_migrations.py` |

Alembic reads `DATABASE_URL` from the environment (`backend/alembic/env.py` → `get_settings()`).

---

## Related docs

- [EnvironmentVariables.md](./EnvironmentVariables.md)
- [Deployment.md](./Deployment.md) — Docker Compose / nginx alternative
- [Backups.md](./Backups.md)
