# QuizArena

Real-time quiz platform for live events — admin quiz builder, participant join flow, presentation display, and WebSocket-driven room synchronization.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite, TanStack Query, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, Alembic |
| Database | SQLite (dev) / PostgreSQL (production) |
| Real-time | Native WebSockets |

## Quick start (local development)

```bash
# Backend
cd backend
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_admin
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
cp .env.example .env
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/api` and `/ws` to the backend.

## Docker (development compose)

```bash
cp .env.example .env
cp backend/.env.example backend/.env
docker compose up --build
```

- Frontend: [http://localhost:8080](http://localhost:8080)
- Backend API: [http://localhost:8000](http://localhost:8000)

## Production deployment

**Recommended:** Neon (Postgres) + Render (API/WebSockets) + Vercel (SPA)

→ Full guide: **[docs/DEPLOY_RENDER_VERCEL.md](docs/DEPLOY_RENDER_VERCEL.md)**

Alternative (single-host Docker Compose + nginx):

```bash
cp .env.example .env          # set POSTGRES_PASSWORD
cp backend/.env.example backend/.env  # set APP_ENV=production, secrets
docker compose -f docker-compose.prod.yml up -d --build
```

See [docs/Deployment.md](docs/Deployment.md) for TLS, scaling, and Docker runbooks.

## Documentation

| Document | Description |
|----------|-------------|
| [Deploy: Render + Neon + Vercel](docs/DEPLOY_RENDER_VERCEL.md) | Recommended cloud deployment |
| [Architecture](docs/Architecture.md) | System overview |
| [Deployment](docs/Deployment.md) | Docker Compose / nginx |
| [Developer Setup](docs/DeveloperSetup.md) | Local dev workflow |
| [Environment Variables](docs/EnvironmentVariables.md) | Configuration reference |
| [API](docs/API.md) | REST & health endpoints |
| [API Spec](docs/API_SPEC.md) | Full API contract |
| [Backups](docs/Backups.md) | Backup, restore, rollback |
| [Contributing](docs/Contributing.md) | Contribution guidelines |
| [Final Polish Audit](docs/FINAL_POLISH_AUDIT.md) | Production readiness |

## Health checks

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/live` | Liveness (process up) |
| `GET /api/v1/ready` | Readiness (database connected) |
| `GET /api/v1/health` | Full health summary |
| `GET /api/v1/metrics` | Lightweight metrics |

## License

Proprietary — internal use unless otherwise specified.
