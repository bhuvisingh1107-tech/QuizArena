# Developer Setup

Local development workflow for QuizArena contributors.

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.12 |
| Node.js | 22 |
| npm | 10+ |

Optional: Docker Compose for full-stack testing against PostgreSQL.

## Clone and configure

```bash
git clone <repo-url> QuizArena
cd QuizArena
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m scripts.seed_admin
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

API docs (debug mode): [http://localhost:8000/docs](http://localhost:8000/docs)

### Frontend

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

App: [http://localhost:5173](http://localhost:5173)

Vite proxies `/api` → `localhost:8000` and `/ws` → backend WebSocket. Leave `VITE_*` vars unset in `.env` to use relative same-origin URLs through the proxy.

## Running tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
npm run build   # production build check
npx tsc -b --noEmit
npm run lint    # oxlint
```

## Database

- **SQLite** (default): file at `backend/quizarena.db`
- **PostgreSQL**: set `DATABASE_URL=postgresql://...` in `backend/.env`

Create a new migration after model changes:

```bash
cd backend
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

Verify head:

```bash
python scripts/verify_migrations.py
```

## Storage

Uploaded media defaults to `../storage` relative to the backend working directory. Override with `STORAGE_PATH` in `.env`.

## Docker alternative

See [Deployment.md](./Deployment.md) for `docker compose up` without installing Python/Node locally.

## Project structure

```
QuizArena/
├── backend/          FastAPI application
├── frontend/         React SPA
├── docs/             Specifications and guides
├── nginx/            Production reverse proxy config
└── storage/          Local media uploads (gitignored)
```

## Further reading

- [EnvironmentVariables.md](./EnvironmentVariables.md)
- [API_SPEC.md](./API_SPEC.md)
- [SOCKET_EVENTS.md](./SOCKET_EVENTS.md)
- [Contributing.md](./Contributing.md)
