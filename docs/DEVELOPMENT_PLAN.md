# QuizArena — Development Plan

| Field | Value |
|-------|-------|
| **Document Title** | QuizArena — Development Plan |
| **Version** | 1.0 |
| **Status** | Draft for Review |
| **Date** | July 31, 2026 |
| **Prepared By** | Software Architecture Team |
| **Architecture Baseline** | [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) v1.0 |
| **Requirements Baseline** | [PROJECT_SPEC.md](./PROJECT_SPEC.md) v1.1 |
| **Related** | [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md), [API_SPEC.md](./API_SPEC.md), [SOCKET_EVENTS.md](./SOCKET_EVENTS.md), [UI_FLOW.md](./UI_FLOW.md) |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals and Non-Goals](#2-goals-and-non-goals)
3. [Delivery Approach](#3-delivery-approach)
4. [Documentation Baseline](#4-documentation-baseline)
5. [Workstreams](#5-workstreams)
6. [Implementation Phases](#6-implementation-phases)
7. [Milestones](#7-milestones)
8. [Capacity and Constraints](#8-capacity-and-constraints)
9. [Known v1 Limitations](#9-known-v1-limitations)
10. [Post-v1 Growth Path](#10-post-v1-growth-path)
11. [Definition of Done](#11-definition-of-done)
12. [Risks](#12-risks)

---

## 1. Overview

This plan sequences implementation of QuizArena v1.0 as a **modular monolith**: one FastAPI backend (REST + native WebSocket + background tasks), one React SPA with three route modules (Admin, Join, Display), SQLite locally / Neon PostgreSQL in production, local file storage behind an abstract interface, deployed to Vercel (frontend) and Render (backend).

It derives only from [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) and the companion docs listed above. It does not introduce product features beyond that baseline.

---

## 2. Goals and Non-Goals

### 2.1 Goals (v1)

- Three synchronized clients: Admin Dashboard, Participant Client, Presentation Screen
- Server-authoritative room, quiz, question, and participant state machines
- Server-side scoring and mandatory leaderboard broadcast after every scored question
- JWT admin auth; participant session tokens; display secret links
- Quiz template CRUD with sections/questions/media; live rooms with session snapshots
- CSV/Excel export and session history
- Capacity: 5 concurrent rooms × 100 participants; ≤ 1s P95 realtime latency targets
- Open-source stack only (CON-005)

### 2.2 Non-Goals (v1)

Explicitly deferred by architecture:

- Redis-backed room runtime / mid-session failover
- Cloud object storage (S3/R2) as active backend (stub only)
- Horizontally scaled WebSocket service
- Multi-admin / multi-tenant hosting
- Socket.IO (native WebSocket chosen)
- CI/CD pipeline (manual git-push deploy; GitHub Actions called out as future)
- Non-English i18n strings; dark theme

---

## 3. Delivery Approach

| Choice | Implication for plan |
|--------|----------------------|
| Modular monolith | Build service modules in dependency order; single deploy unit |
| Content vs session separation | Quiz CRUD before live rooms; snapshot on room create |
| Thin clients | Backend FSMs and scoring before polished live UI |
| In-memory room context | Live path after persistence model exists; accept restart = session loss |
| Storage interface | Local backend first; keep `cloud.py` stub unused |

Monorepo layout target: `frontend/`, `backend/`, `docs/`, `storage/` per architecture §16.

---

## 4. Documentation Baseline

| Document | Role |
|----------|------|
| [PROJECT_SPEC.md](./PROJECT_SPEC.md) | What the system must do (SRS) |
| [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) | How the system is structured |
| [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) | Entities, relationships, constraints |
| [API_SPEC.md](./API_SPEC.md) | REST resource groups and conventions |
| [SOCKET_EVENTS.md](./SOCKET_EVENTS.md) | WebSocket protocol and events |
| [UI_FLOW.md](./UI_FLOW.md) | Client routes and flows |

Physical SQL columns, OpenAPI field schemas, and remaining WS payload shapes are refined during implementation without expanding scope.

---

## 5. Workstreams

| Workstream | Owns (from architecture) |
|------------|--------------------------|
| **Backend core** | FastAPI app, config, middleware (CORS, request ID, JWT, rate limit, errors), SQLAlchemy, Alembic |
| **Auth & security** | AuthService, JWT, password hashing, SecurityLog, seed admin |
| **Content** | Quiz / Question / Section services, QuizConfig, validation gate Draft→Ready |
| **Media** | FileStorageService, local backend, media routes |
| **Live session** | RoomService, ParticipantService, state machines, TimerService, in-memory room context |
| **Scoring & leaderboard** | ScoringService (SRS §12), LeaderboardService, broadcast hooks |
| **Realtime** | WebSocket manager, resync, heartbeats |
| **History & export** | Session history APIs, ExportService (CSV + Excel) |
| **Frontend admin** | `/admin/*` module: auth, library, editor, host controls, history |
| **Frontend join** | `/join/*`: code, name/email, lobby, play, reconnect |
| **Frontend display** | `/display/:token`: read-only modes |
| **Deploy** | Vercel + Render + Neon; env vars; health check; persistent disk |

---

## 6. Implementation Phases

### Phase A — Foundations

- Monorepo skeleton (`frontend/`, `backend/`, `storage/`, `docs/`)
- FastAPI entry, config via env (`DATABASE_URL`, JWT, CORS, storage)
- SQLAlchemy + Alembic; SQLite local / Postgres-ready models
- Middleware stack; `GET /api/v1/health`
- Seed admin script
- Vite React SPA shell, router, shared Axios/Zod layout
- Local run: Vite `:5173`, Uvicorn `:8000`

### Phase B — Admin auth and content domain

- `POST /admin/login`, logout, JWT guards, SecurityLog
- Quiz / Section / Question / AnswerOption / QuizConfig persistence and REST
- Archive, duplicate, validate, soft delete, InUse lock rules
- Media upload/delete/serve (local storage)
- Admin UI: login, quiz library, editor, preview (Ready solo mode)

### Phase C — Live room engine (backend)

- LiveRoom + session snapshot (SessionQuestion/Option, RoomConfig)
- Room FSM: Setup → Lobby → Active ↔ Paused → SectionBreak → Completed → Closed
- Participant join REST (rate limited), session tokens, ban list, uniqueness
- Participant FSM and kick/ban
- TimerService; ScoringService; LeaderboardService
- WebSocket connect/auth per role; RESYNC; heartbeats
- Named broadcasts (`room:*`, `section:*`, `question:scored`, `leaderboard:updated`, presence)
- Single active room per admin enforcement

### Phase D — Three-client live UX

- Admin live control + participant monitor panel
- Participant join (≤ 3 screens), lobby, play, buzzer, leaderboard, reconnect
- Display secret-link client: lobby, question, timer, reveal, section/live leaderboard, podium
- Wire timer display to `timerEndsAt` / pause fields
- Ensure leaderboard always reaches all three clients after scoring

### Phase E — History, export, harden, deploy

- Session history browse/delete
- CSV/Excel export generation and download
- Settings (platform branding/configuration)
- Structured logging; security event coverage
- Production: Neon, Render (persistent disk, WS-capable plan), Vercel
- Alembic on deploy; health probe; env vars per architecture §18.3
- Manual main-branch deploy (no CI required for v1)

---

## 7. Milestones

| Milestone | Outcome |
|-----------|---------|
| **M0** | Repo runs locally; health OK; docs linked |
| **M1** | Admin can log in; create/edit/validate quizzes with media |
| **M2** | Backend can run a full room lifecycle with scoring over WebSocket (test clients acceptable) |
| **M3** | All three UI clients complete a live session together |
| **M4** | History + export + production deploy verified against capacity assumptions |

---

## 8. Capacity and Constraints

| Dimension | v1 target |
|-----------|-----------|
| Concurrent live rooms | 5 |
| Participants per room | 100 |
| Realtime latency | ≤ 1 second P95 |
| Questions per quiz | ≤ 100 |
| Deploy | Git push → Vercel auto + Render auto (migrate then start) |

---

## 9. Known v1 Limitations

| Limitation | Accepted impact |
|------------|-----------------|
| Single backend instance / in-memory rooms | Mid-session loss on restart |
| Local/Render disk storage | Files tied to instance; monitor disk |
| Single admin host | One actively controlled room |
| No horizontal WebSocket scaling | Stay within 5×100 on one process |
| No CI/CD in v1 | Tests run locally before push |

---

## 10. Post-v1 Growth Path

From architecture §15.5 (not in v1 delivery):

1. Cloud file storage (S3/R2)  
2. Redis for room runtime + session store  
3. Separate WebSocket service (horizontal scaling)  
4. Multi-admin, multi-tenant architecture  

---

## 11. Definition of Done

- Behavior matches SRS + architecture for in-scope flows (auth, quiz CRUD, live room, join, display, scoring, leaderboard, export, history)
- Clients remain thin; server owns transitions, timers, scores
- Session snapshot isolation from template edits verified
- Reconnect + RESYNC verified for participant (and admin/display reconnect paths)
- `GET /api/v1/health` used by Render; production env vars set
- Docs updated if implementation clarifies schemas without changing scope

---

## 12. Risks

| Risk | Mitigation aligned with architecture |
|------|--------------------------------------|
| Realtime complexity | Room-scoped WS; in-memory context; mandatory causal ordering |
| Schema churn | Content vs session separation; Alembic review workflow |
| Scope creep | Reject features outside SRS/architecture (esp. multi-tenant, Redis, Socket.IO) |
| Render sleep / WS timeouts | Paid plan for live events; verify proxy timeouts |
| Disk / file loss | Storage abstraction; monitor persistent disk; cleanup orphans |

---

*End of Document*
