# API Overview

QuizArena exposes a versioned REST API and a native WebSocket endpoint. The authoritative contract is [API_SPEC.md](./API_SPEC.md).

## Base URLs

| Environment | REST | WebSocket |
|-------------|------|-----------|
| Local dev (Vite proxy) | `/api/v1` | `ws://localhost:5173/ws` |
| Local backend direct | `http://localhost:8000/api/v1` | `ws://localhost:8000/ws` |
| Production (nginx) | `https://<domain>/api/v1` | `wss://<domain>/ws` |

## Authentication

- **Admin**: `POST /api/v1/admin/login` → JWT Bearer on subsequent requests
- **Participant**: session token from join flow → Bearer on participant endpoints
- **Display**: secret token in URL / WebSocket query param

## Resource groups

| Prefix | Description |
|--------|-------------|
| `/api/v1/admin/*` | Authentication |
| `/api/v1/quizzes` | Quiz CRUD and validation |
| `/api/v1/live-rooms` | Session lifecycle |
| `/api/v1/join` | Participant join |
| `/api/v1/participants` | Participant actions |
| `/api/v1/media` | Media upload and content |
| `/api/v1/dashboard` | Admin dashboard stats |

See [API_SPEC.md](./API_SPEC.md) for request/response schemas, status codes, and pagination.

## Health & observability

These endpoints are unauthenticated and suitable for load balancers and monitoring.

### `GET /api/v1/live`

**Liveness** — process is running. Does not check dependencies.

```json
{ "status": "alive", "uptimeSeconds": 123.4 }
```

### `GET /api/v1/ready`

**Readiness** — returns `200` when the database is reachable, `503` otherwise.

```json
{ "status": "ready", "database": "connected", "meta": { "requestId": "..." } }
```

### `GET /api/v1/health`

**Full health** — database status, WebSocket connection counts, app environment.

```json
{
  "data": {
    "status": "healthy",
    "database": "connected",
    "timestamp": "2026-07-31T12:00:00Z",
    "appEnv": "production",
    "websocket": { "activeRooms": 2, "connections": 45 },
    "uptimeSeconds": 3600
  },
  "meta": { "requestId": "..." }
}
```

### `GET /api/v1/metrics`

Lightweight JSON metrics (uptime, WebSocket pool snapshot).

## WebSocket

Connect to `/ws` with role-specific query parameters. Event catalog: [SOCKET_EVENTS.md](./SOCKET_EVENTS.md).

## OpenAPI

When `DEBUG=true`, interactive docs are available at `/docs` and `/redoc` on the backend port.
