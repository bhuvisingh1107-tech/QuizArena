# QuizArena — System Architecture Document

| Field | Value |
|-------|-------|
| **Document Title** | QuizArena — System Architecture Document |
| **Version** | 1.0 |
| **Status** | Draft for Review |
| **Date** | July 31, 2026 |
| **Prepared By** | Software Architecture Team |
| **Requirements Baseline** | [PROJECT_SPEC.md](./PROJECT_SPEC.md) v1.1 |

---

## Table of Contents

1. [Overall System Architecture](#1-overall-system-architecture)
2. [Client Architecture](#2-client-architecture)
3. [Backend Architecture](#3-backend-architecture)
4. [Database Architecture](#4-database-architecture)
5. [Authentication Flow](#5-authentication-flow)
6. [WebSocket Architecture](#6-websocket-architecture)
7. [Room Lifecycle](#7-room-lifecycle)
8. [Quiz Lifecycle](#8-quiz-lifecycle)
9. [Participant Lifecycle](#9-participant-lifecycle)
10. [File Upload Architecture](#10-file-upload-architecture)
11. [API Design Principles](#11-api-design-principles)
12. [Database Relationships](#12-database-relationships)
13. [Error Handling Strategy](#13-error-handling-strategy)
14. [Security Considerations](#14-security-considerations)
15. [Scalability Considerations](#15-scalability-considerations)
16. [Folder Structure](#16-folder-structure)
17. [Technology Decisions](#17-technology-decisions)
18. [Deployment Architecture](#18-deployment-architecture)

---

## 1. Overall System Architecture

QuizArena is a three-client, single-backend real-time quiz platform. All clients are React single-page applications deployed to Vercel. The backend is a FastAPI application deployed to Render, backed by Neon PostgreSQL in production and SQLite in local development. Real-time synchronization is achieved through WebSocket connections co-located with the REST API on the same backend process.

### 1.1 Architectural Style

The system follows a **modular monolith** architecture for v1.0:

- One deployable backend service containing REST API, WebSocket handler, business logic, and background tasks
- One deployable frontend application containing three client experiences via route-based separation
- One relational database for persistent state
- Local filesystem for media storage (abstracted behind a storage interface for future cloud migration)

This style satisfies SRS scalability targets (5 concurrent rooms, 100 participants per room) while minimizing operational complexity for a single-administrator SaaS deployment.

### 1.2 High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT TIER (Vercel)                           │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  Admin Dashboard  │  │ Participant Client│  │  Presentation Screen    │  │
│  │  /admin/*         │  │  /join/*          │  │  /display/:secretToken  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────────┬─────────────┘  │
│           │                     │                           │                │
│           │    React + TypeScript + Tailwind CSS            │                │
│           │    React Router | TanStack Query | Axios        │                │
│           │    React Hook Form + Zod                        │                │
└───────────┼─────────────────────┼───────────────────────────┼────────────────┘
            │                     │                           │
            │  HTTPS REST         │  HTTPS REST               │  HTTPS REST
            │  WSS                │  WSS                      │  WSS
            │                     │                           │
┌───────────┼─────────────────────┼───────────────────────────┼────────────────┐
│           ▼                     ▼                           ▼                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     BACKEND TIER (Render)                             │   │
│  │                                                                       │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────────┐  │   │
│  │  │  REST API    │  │  WebSocket   │  │  Background Tasks           │  │   │
│  │  │  (FastAPI)   │  │  Manager     │  │  (timers, scoring, export)  │  │   │
│  │  └──────┬──────┘  └──────┬───────┘  └──────────────┬──────────────┘  │   │
│  │         │                │                         │                 │   │
│  │         └────────────────┼─────────────────────────┘                 │   │
│  │                          ▼                                           │   │
│  │  ┌───────────────────────────────────────────────────────────────┐   │   │
│  │  │                    SERVICE LAYER                               │   │   │
│  │  │  Auth | Quiz | Question | Room | Participant | Scoring        │   │   │
│  │  │  Leaderboard | Export | File Storage | State Machine          │   │   │
│  │  └───────────────────────────┬───────────────────────────────────┘   │   │
│  │                              ▼                                       │   │
│  │  ┌───────────────────────────────────────────────────────────────┐   │   │
│  │  │              DATA ACCESS LAYER (SQLAlchemy)                    │   │   │
│  │  └───────────────────────────┬───────────────────────────────────┘   │   │
│  └──────────────────────────────┼───────────────────────────────────────┘   │
│                                 │                                           │
│  ┌──────────────────────────────┼───────────────────────────────────────┐   │
│  │  STORAGE TIER                ▼                                       │   │
│  │  ┌─────────────────────┐  ┌─────────────────────────────────────┐  │   │
│  │  │  Neon PostgreSQL     │  │  Local File Storage (Render disk)   │  │   │
│  │  │  (production)        │  │  images/ | audio/ | branding/       │  │   │
│  │  │  SQLite (dev)        │  │  [future: S3 / Cloudflare R2]       │  │   │
│  │  └─────────────────────┘  └─────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Communication Patterns

| Pattern | Used For | Protocol |
|---------|----------|----------|
| **Request-Response** | CRUD operations, authentication, file uploads, exports, join validation | HTTPS REST |
| **Publish-Subscribe (room-scoped)** | Live session events: state changes, questions, timers, scores, leaderboard | WSS |
| **Server-Authoritative State** | Room state machine, question timers, scoring, buzzer lock | Backend-enforced |
| **Client-Optimistic UI** | Answer selection before submit (not score or rank) | Local state, server confirms |

### 1.4 Design Principles

| Principle | Application |
|-----------|-------------|
| **Server authority** | All state transitions, scoring, and timer logic execute on the backend; clients are renderers |
| **Thin clients** | Clients display state and capture input; they do not compute scores or enforce rules |
| **Single source of truth** | PostgreSQL for durable state; in-memory room cache for active session hot path |
| **Fail-safe defaults** | Invalid transitions rejected; disconnected clients resync from server snapshot |
| **Separation of concerns** | Quiz content (templates) is decoupled from live session state (runtime instances) |
| **Storage abstraction** | File operations go through a storage interface to enable future cloud migration without business logic changes |

### 1.5 Traceability to SRS

This architecture directly supports the following SRS constraints and objectives:

- **OBJ-003 / NFR-001:** Sub-1-second real-time delivery via room-scoped WebSocket broadcasts and in-memory session cache
- **OBJ-004 / NFR-031:** 5 concurrent rooms × 100 participants within modular monolith capacity
- **CON-001–004:** Approved technology stack across all tiers
- **Section 12–13 (SRS):** Server-side scoring engine and state machines as dedicated backend modules
- **FR-091:** Leaderboard always broadcast to all three client types on every scored question

---

## 2. Client Architecture

All three clients share a single React application deployed to Vercel. Route-based code splitting separates Admin Dashboard, Participant Client, and Presentation Screen experiences while maximizing shared component and utility reuse.

### 2.1 Application Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    QuizArena Frontend (SPA)                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  App Shell                                           │  │
│  │  React Router | TanStack Query Provider | Auth Context│  │
│  └────────────────────────┬────────────────────────────┘  │
│                           │                                │
│         ┌─────────────────┼─────────────────┐              │
│         ▼                 ▼                 ▼              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ Admin Module │  │ Join Module │  │ Display Module  │   │
│  │ /admin/*     │  │ /join/*     │  │ /display/:token │   │
│  └─────────────┘  └─────────────┘  └─────────────────┘   │
│         │                 │                 │              │
│         └─────────────────┼─────────────────┘              │
│                           ▼                                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Shared Layer                                        │  │
│  │  UI Components | Hooks | WebSocket Client | Types    │  │
│  │  Axios Client | Zod Schemas | Utils                  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Route Map

| Route Prefix | Client | Auth Required | Description |
|--------------|--------|---------------|-------------|
| `/admin/login` | Admin Dashboard | No | Administrator login |
| `/admin/*` | Admin Dashboard | JWT | Quiz management, live hosting, history, exports |
| `/join` | Participant Client | No | Room code entry |
| `/join/:roomCode` | Participant Client | No | QR deep-link join |
| `/join/:roomCode/lobby` | Participant Client | Session token | Waiting lobby |
| `/join/:roomCode/play` | Participant Client | Session token | Live gameplay |
| `/display/:secretToken` | Presentation Screen | Secret token | Full-screen audience display |

### 2.3 State Management Strategy

| State Type | Mechanism | Scope |
|------------|-----------|-------|
| **Server data (REST)** | TanStack Query | Quizzes, questions, session history, exports |
| **Auth state** | React Context | JWT token, admin session |
| **Participant session** | Local storage + Context | Participant session token, room identity |
| **Live session state** | WebSocket-driven React state | Room state, current question, timer, leaderboard |
| **Form state** | React Hook Form + Zod | Quiz editor, question editor, join form, login |
| **UI state** | Component-local state | Modals, toggles, loading indicators |

**Design rule:** TanStack Query manages REST-fetched data with cache invalidation on mutations. Live session data is never stored in TanStack Query cache — it flows exclusively through the WebSocket connection into dedicated live-session state hooks.

### 2.4 Admin Dashboard Module

**Responsibilities:**

- Administrator authentication and session management
- Quiz and question CRUD with section organization
- Quiz preview (solo mode)
- Live room creation, hosting, and session control
- Real-time participant monitoring panel
- Session history browsing and data deletion
- CSV/Excel export triggering and download

**Key UI areas:**

```
┌────────────────────────────────────────────────────────────┐
│  Admin Dashboard                                            │
│  ┌──────────┬──────────────────────────────────────────┐   │
│  │ Sidebar   │  Main Content Area                       │   │
│  │           │                                          │   │
│  │ Dashboard │  [Quiz Library | Quiz Editor | Preview]  │   │
│  │ Quizzes   │  [Live Room Control | Monitor Panel]     │   │
│  │ History   │  [Session Results | Export]              │   │
│  │ Settings  │                                          │   │
│  └──────────┴──────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### 2.5 Participant Client Module

**Responsibilities:**

- Room code entry and QR deep-link handling
- Name and email collection with validation
- Lobby waiting view
- Live question display with answer selection and explicit submit
- Buzzer interaction on buzzer question types
- Live leaderboard display (always visible after each question)
- Automatic WebSocket reconnection with state resync
- Final rank and score at session end

**Join flow (≤ 3 screens per NFR-040):**

```
Screen 1: Enter room code (or QR auto-fill)
    │
    ▼
Screen 2: Enter display name + email
    │
    ▼
Screen 3: Lobby (waiting for admin to start)
    │
    ▼
Gameplay view (question + leaderboard)
```

### 2.6 Presentation Screen Module

**Responsibilities:**

- Render via secret share link (no login)
- Full-screen, large-format layout optimized for TVs and projectors
- Display modes driven by room state: lobby, question, timer, answer reveal, section leaderboard, live leaderboard, podium
- Quiz title, room code, platform logo, and per-quiz branding
- No admin controls; no participant emails

**Display layout concept:**

```
┌────────────────────────────────────────────────────────────┐
│  [Logo]   Quiz Title                    Room Code: ABC123  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│                    QUESTION / LEADERBOARD                   │
│                       (primary content)                     │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  [Timer bar]                              [Participant #]  │
└────────────────────────────────────────────────────────────┘
```

### 2.7 Shared Frontend Concerns

| Concern | Approach |
|---------|----------|
| **HTTP client** | Axios instance with interceptors for JWT attachment (admin) and error normalization |
| **Validation** | Zod schemas shared between forms and API response parsing |
| **WebSocket client** | Custom hook wrapping native WebSocket with auto-reconnect, heartbeat, and room resync |
| **Timer display** | Client renders countdown from server-provided `endsAt` timestamp; server authority on expiry |
| **Responsive design** | Tailwind CSS responsive utilities; equal priority for desktop and mobile on Admin and Participant |
| **i18n readiness** | String extraction pattern prepared; English-only strings in v1 |
| **Theming** | Light theme only; Tailwind config with design tokens |

---

## 3. Backend Architecture

The backend is a FastAPI modular monolith organized into layered modules with clear separation between HTTP handling, business logic, and data access.

### 3.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                      │
│  REST Routers  |  WebSocket Endpoints  |  Middleware         │
│  Request validation (Pydantic)  |  Auth guards              │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                       SERVICE LAYER                           │
│                                                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │ AuthService  │ │ QuizService │ │ QuestionService         │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │ RoomService  │ │ Participant │ │ ScoringService          │ │
│  │             │ │ Service     │ │                         │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐ │
│  │ Leaderboard  │ │ ExportService│ │ FileStorageService     │ │
│  │ Service     │ │             │ │                         │ │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ State Machine Engine                                     │ │
│  │ Room | Quiz | Question | Participant transition logic    │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Timer Service (server-authoritative question timers)     │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    DATA ACCESS LAYER                         │
│  SQLAlchemy Models  |  Repository classes  |  Unit of Work  │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  PostgreSQL / SQLite          |        Local File Storage     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Core Backend Modules

| Module | Responsibility |
|--------|----------------|
| **Auth** | Admin login, JWT issuance and validation, password verification, security event logging |
| **Quiz** | Quiz CRUD, archive, duplicate, validation, state transitions (Draft/Ready/InUse/Archived) |
| **Question** | Question CRUD within quizzes, section organization, ordering, validation, media references |
| **Room** | Live room creation, room code generation, secret link generation, room state machine, session control |
| **Participant** | Join validation, session token issuance, reconnection, kick/ban, participant state tracking |
| **Scoring** | Base points, time bonus, streak bonus computation per SRS Section 12; all server-side |
| **Leaderboard** | Rank computation with tie-breaking, section-level aggregation, broadcast payload preparation |
| **Export** | CSV and Excel generation from persisted session data |
| **FileStorage** | Upload validation, local storage, URL generation; abstracted interface for future cloud |
| **WebSocket** | Connection management, room-scoped pub/sub, event serialization, resync snapshot |
| **Timer** | Server-authoritative question timers using async scheduling; pause/resume freeze support |

### 3.3 Room Session Runtime Model

Active live sessions maintain a **room runtime context** in backend memory for low-latency operations:

```
┌─────────────────────────────────────────────────────────┐
│  Room Runtime Context (in-memory, per active room)       │
│                                                         │
│  roomState: Setup | Lobby | Active | Paused | ...       │
│  currentQuestionIndex, currentQuestionState             │
│  timerHandle (endsAt timestamp, remaining on pause)     │
│  connectedClients: { admin, participants[], display }   │
│  buzzerLock: participantId | null                       │
│  liveLeaderboard: sorted participant scores             │
│  participantStates: Map<participantId, state>          │
└─────────────────────────────────────────────────────────┘
         │
         │  persisted on state transitions
         ▼
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL (durable session record)                     │
└─────────────────────────────────────────────────────────┘
```

**Persistence strategy:**

- Runtime context holds hot path data for sub-1-second event delivery
- State transitions write through to PostgreSQL immediately
- Participant responses and scores persist on each scored question
- Full session snapshot persisted before Completed state
- On backend restart mid-session: session is lost (acceptable for v1 best-effort availability); future scope may add Redis-backed runtime state

### 3.4 Scoring Engine

The scoring engine is a pure backend module implementing SRS Section 12 rules:

```
Answer Submission Received
        │
        ▼
┌───────────────────┐
│ Validate: question │──▶ Reject if question not Open/BuzzerLocked
│ is accepting input │    or participant not eligible (buzzer)
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Grade answer       │──▶ All-or-nothing MC comparison
│ (correct/incorrect)│
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Compute base points│──▶ Full value if correct, 0 otherwise
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Compute time bonus │──▶ If enabled + correct + timer active
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Compute streak     │──▶ If enabled + correct, increment streak
│ bonus / reset      │    If incorrect/unanswered, reset streak
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Update participant │──▶ Persist response + points
│ score + streak     │
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Recompute          │──▶ Full room leaderboard with tie-breaking
│ leaderboard        │
└────────┬──────────┘
         ▼
┌───────────────────┐
│ Broadcast          │──▶ question:scored + leaderboard:updated
│ to all room clients│    to admin, all participants, display
└───────────────────┘
```

### 3.5 Background Processing

| Task | Trigger | Execution |
|------|---------|-----------|
| **Question timer expiry** | Question enters Open state with timer configured | Async timer fires, closes question, triggers scoring pipeline |
| **Auto-advance** | Timer expiry + quiz configured for automatic advance | State machine advances to next question after scoring |
| **Export generation** | Admin requests export | Async file build, temporary download URL or direct stream |
| **Room code cleanup** | Room transitions to Closed | Mark codes expired in database |

### 3.6 Middleware Stack

| Middleware | Purpose |
|------------|---------|
| **CORS** | Allow Vercel frontend origin; restrict to configured domains |
| **Request ID** | Attach correlation ID for structured logging |
| **JWT Auth** | Validate admin JWT on protected REST routes |
| **Rate Limiter** | Protect login and join endpoints (NFR-023) |
| **Error Handler** | Normalize exceptions to consistent error response format |

---

## 4. Database Architecture

### 4.1 Database Strategy

| Environment | Engine | Hosting | Purpose |
|-------------|--------|---------|---------|
| **Development** | SQLite | Local filesystem | Fast local iteration, zero infrastructure |
| **Production** | PostgreSQL | Neon | Managed, serverless-compatible PostgreSQL |
| **Test** | SQLite (in-memory) | CI runner | Isolated test execution |

SQLAlchemy serves as the ORM for both environments. Alembic manages schema migrations. Environment selection is configuration-driven via a `DATABASE_URL` environment variable.

### 4.2 Data Categories

The database stores five categories of data:

```
┌─────────────────────────────────────────────────────────────┐
│                     DATABASE DATA DOMAINS                    │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  Identity        │  │  Content         │                   │
│  │  Admin account   │  │  Quizzes         │                   │
│  │  Security logs   │  │  Sections        │                   │
│  │                  │  │  Questions       │                   │
│  │                  │  │  Answer options  │                   │
│  └─────────────────┘  └─────────────────┘                   │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  Session Runtime │  │  Media Metadata  │                   │
│  │  Live rooms      │  │  File references │                   │
│  │  Participants    │  │  Storage paths   │                   │
│  │  Responses       │  │  MIME types      │                   │
│  │  Scores          │  │  File sizes      │                   │
│  │  Session history │  │                  │                   │
│  └─────────────────┘  └─────────────────┘                   │
│                                                             │
│  ┌─────────────────┐                                          │
│  │  Configuration   │                                          │
│  │  Platform settings│                                         │
│  │  Branding defaults│                                         │
│  └─────────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Content vs. Session Separation

A critical architectural decision is the separation of **quiz templates** (reusable content) from **session instances** (runtime data):

```
Quiz Template (durable content)          Session Instance (runtime snapshot)
─────────────────────────────           ─────────────────────────────────
Quiz                                    Live Room
  └── Section                             └── Session Participant
        └── Question                            └── Session Response
              └── Answer Option                         └── Score Record
```

When a live room is created from a quiz, the backend creates a **session snapshot** of the quiz structure. Changes to the quiz template after room creation do not affect an active or completed session. This ensures session history integrity and export consistency (NFR-072).

### 4.4 Migration Strategy

| Aspect | Approach |
|--------|----------|
| **Tool** | Alembic with autogenerate review workflow |
| **Naming** | Timestamp-prefixed revision files |
| **Development** | Migrations applied on startup or via CLI |
| **Production** | Migrations run as part of Render deploy pipeline before app start |
| **Rollback** | Downgrade scripts maintained for each revision |
| **Seeding** | Admin account seeded via CLI command or startup script (ASM-002) |

### 4.5 Indexing Strategy (Conceptual)

Indexes will be planned around these query patterns (detailed index definitions deferred to schema design phase):

- Quiz library listing and search by title/status
- Live room lookup by room code (join flow hot path)
- Session history listing by date
- Participant lookup by room + email (uniqueness check, reconnection)
- Session responses by room + participant (export generation)

---

## 5. Authentication Flow

QuizArena uses two distinct authentication models: JWT for the administrator and session tokens for participants. The Presentation Screen uses a secret link token.

### 5.1 Administrator Authentication (JWT)

```
┌──────────┐                ┌──────────┐                ┌──────────┐
│  Admin    │                │  Backend  │                │  Database │
│  Client   │                │          │                │          │
└─────┬────┘                └─────┬────┘                └─────┬────┘
      │                           │                           │
      │  POST /admin/login        │                           │
      │  { username, password }   │                           │
      │──────────────────────────▶│                           │
      │                           │  Verify credentials        │
      │                           │──────────────────────────▶│
      │                           │◀──────────────────────────│
      │                           │                           │
      │                           │  Log security event        │
      │                           │──────────────────────────▶│
      │                           │                           │
      │  200 { accessToken,       │                           │
      │        expiresAt }        │                           │
      │◀──────────────────────────│                           │
      │                           │                           │
      │  Store JWT in memory      │                           │
      │  (Axios interceptor)      │                           │
      │                           │                           │
      │  Subsequent requests:     │                           │
      │  Authorization: Bearer    │                           │
      │  <JWT>                    │                           │
      │──────────────────────────▶│                           │
      │                           │  Validate JWT signature    │
      │                           │  Check expiration (~8hr)   │
      │                           │  Allow / reject            │
      │                           │                           │
      │  POST /admin/logout       │                           │
      │──────────────────────────▶│                           │
      │                           │  Log security event        │
      │                           │  Client discards token     │
      │                           │                           │
```

**JWT payload (conceptual fields):**

| Field | Purpose |
|-------|---------|
| `sub` | Administrator identifier |
| `iat` | Issued at timestamp |
| `exp` | Expiration (~8 hours, no refresh in v1) |
| `role` | `admin` (single role in v1) |

### 5.2 Participant Session Authentication

Participants do not receive JWTs. On successful join, the backend issues a **participant session token** tied to the room and participant record:

```
Participant Join Flow (Auth)
─────────────────────────────

1. Participant submits room code + name + email
2. Backend validates:
   - Room exists and is not Closed
   - Room lobby is open (or reconnection allowed)
   - Name unique within room
   - Email unique within room (or matches existing for reconnection)
   - Email not on ban list for this room
3. Backend creates or restores participant record
4. Backend returns participant session token
5. Participant client stores token (session storage)
6. Token included in:
   - REST requests (header or query param)
   - WebSocket connection handshake (query param or first message)
7. Backend validates token on every participant action
```

### 5.3 Presentation Screen Authentication

```
Display Access Flow
───────────────────

1. Admin creates live room → backend generates secretToken (high entropy)
2. Admin copies share link: https://app.quizarena.com/display/{secretToken}
3. Display client loads with secretToken from URL
4. Backend validates secretToken maps to an active room
5. Display client connects to WebSocket with secretToken
6. No JWT or participant token required
7. Display client receives read-only room events
```

### 5.4 Authentication Matrix

| Client | Auth Mechanism | Scope | Expiry |
|--------|---------------|-------|--------|
| **Admin Dashboard** | JWT (Bearer header) | All admin REST + WebSocket | ~8 hours |
| **Participant Client** | Session token | Room-scoped actions + WebSocket | Room session lifetime |
| **Presentation Screen** | Secret link token | Read-only WebSocket + initial REST snapshot | Room session lifetime |

---

## 6. WebSocket Architecture

Real-time synchronization uses native WebSockets via FastAPI's WebSocket support. All live session events flow through a room-scoped pub/sub channel.

### 6.1 Connection Model

```
                    ┌─────────────────────────────┐
                    │     WebSocket Manager        │
                    │                             │
                    │  rooms: Map<roomId, Set>    │
                    │    ├── admin: WSConnection   │
                    │    ├── display: WSConnection │
                    │    └── participants: Map      │
                    │         <participantId, WS>  │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        Admin Client       Participant Clients    Display Client
        (1 per room)       (up to 100)            (1 per room)
```

### 6.2 Connection Lifecycle

```
CONNECT
  │
  ├── Admin: authenticate JWT → join room admin channel
  ├── Participant: authenticate session token → join room participant channel
  └── Display: authenticate secretToken → join room display channel
  │
  ▼
SERVER sends RESYNC snapshot (full room state for client type)
  │
  ▼
ACTIVE (bidirectional for admin/participant; receive-only for display)
  │
  ├── Heartbeat ping/pong every 30s
  ├── Client events → backend validates → state change → broadcast
  └── Server events → broadcast to all room clients
  │
  ▼
DISCONNECT
  │
  ├── Admin: log disconnect; room continues (admin may reconnect)
  ├── Participant: mark Disconnected; allow auto-reconnect with resync
  └── Display: remove from channel; display may reconnect freely
```

### 6.3 Event Categories

Events are categorized by direction and purpose. Event names and payloads will be defined in the API specification phase; architecturally, they group as follows:

| Category | Direction | Examples |
|----------|-----------|---------|
| **Room state** | Server → All | Room state changed, lobby opened/closed, session started/paused/ended |
| **Question** | Server → All | Question presented, timer started/tick/expired, answer revealed |
| **Participant action** | Client → Server | Join, submit answer, buzz |
| **Participant feedback** | Server → Client | Buzz accepted/rejected, answer recorded |
| **Scoring** | Server → All | Question scored, streak updated |
| **Leaderboard** | Server → All | Leaderboard updated (after every question, mandatory) |
| **Participant presence** | Server → Admin | Participant joined, disconnected, reconnected, kicked |
| **Admin control** | Client → Server | Start, pause, resume, skip, advance, end, kick, ban |
| **Section** | Server → All | Section break started, section leaderboard displayed |
| **Sync** | Server → Client | Full state resync on connect/reconnect |

### 6.4 Broadcast Rules

| Rule | Description |
|------|-------------|
| **Room-scoped isolation** | Events are never broadcast across room boundaries |
| **Leaderboard mandatory** | Every `question:scored` event is followed by `leaderboard:updated` to all three client types |
| **Display is read-only** | Display channel receives all broadcast events but sends no control events |
| **Admin-only events** | Participant emails and kick/ban confirmations sent only to admin channel |
| **Participant-specific** | Buzz accept/reject sent only to the target participant (plus admin monitoring) |
| **Ordering guarantee** | Events for a single room are emitted in causal order; clients apply sequentially |

### 6.5 Reconnection and Resync

```
Participant Disconnects
        │
        ▼
Client detects WebSocket close
        │
        ▼
Auto-reconnect with exponential backoff (1s, 2s, 4s, max 10s)
        │
        ▼
On reconnect: send session token
        │
        ▼
Server validates token → sends RESYNC payload:
  - Current room state
  - Current question state + remaining timer
  - Participant's own score, streak, rank
  - Current leaderboard
  - Whether participant already answered current question
        │
        ▼
Client restores UI to match server state
```

### 6.6 Timer Synchronization

Timers are server-authoritative (ASM-007):

- Server sets `timerEndsAt` (absolute UTC timestamp) when question opens
- Broadcast includes `timerEndsAt` to all clients
- Clients compute display countdown locally from `timerEndsAt`
- Server timer task fires at expiry regardless of client state
- On pause: server broadcasts `timerPausedAt` with remaining milliseconds; clients freeze display
- On resume: server broadcasts new `timerEndsAt`; clients resume countdown

---

## 7. Room Lifecycle

Room lifecycle implements SRS Section 13.1 state model. The backend Room Service owns all transitions.

### 7.1 State Diagram

```
                          ┌─────────┐
                          │  Setup  │
                          └────┬────┘
                               │ admin: openLobby
                               ▼
                          ┌─────────┐
               ┌─────────│  Lobby  │──────────┐
               │         └────┬────┘          │
               │ admin:       │ admin:        │ admin:
               │ closeRoom    │ startSession  │ closeRoom
               │              ▼               │
               │         ┌─────────┐          │
               │         │ Active  │◀────┐    │
               │         └────┬────┘     │    │
               │    admin:    │          │    │
               │    pause     │ admin:   │admin:resume
               │              ▼          │    │
               │         ┌─────────┐    │    │
               │         │ Paused  │────┘    │
               │         └────┬────┘         │
               │              │ admin: end   │
               │    admin:    │              │
               │    end       ▼              │
               │         ┌───────────┐       │
               │         │ Section   │       │
               │         │ Break     │──▶ (back to Active)
               │         └───────────┘       │
               │              │              │
               │              ▼              │
               │         ┌───────────┐       │
               │         │ Completed │       │
               │         └─────┬─────┘       │
               │               │ admin:      │
               │               │ closeRoom   │
               ▼               ▼             ▼
          ┌─────────────────────────────────────┐
          │              Closed                  │
          └─────────────────────────────────────┘
```

### 7.2 Transition Ownership

| Transition | Trigger | Backend Actions |
|------------|---------|-----------------|
| **Setup → Lobby** | Admin opens lobby | Generate room code + QR + secret link; set lobby sub-state to Open; broadcast `room:lobbyOpened` |
| **Lobby → Active** | Admin starts session | Create session snapshot from quiz; set first question Pending; broadcast `room:sessionStarted` |
| **Active → Paused** | Admin pauses | Freeze timer; block submissions; broadcast `room:paused` with frozen state |
| **Paused → Active** | Admin resumes | Restore timer; broadcast `room:resumed` |
| **Active → SectionBreak** | Last question in section scored | Compute section leaderboard; broadcast `section:break` |
| **SectionBreak → Active** | Admin advances section | Set next section's first question Pending; broadcast `section:continued` |
| **Active → Completed** | Admin ends session | Persist all data; compute final ranks; broadcast `room:completed` + podium data |
| **Lobby/Completed → Closed** | Admin closes room | Expire room code and tokens; release runtime context; mark quiz InUse → Ready |
| **Active → Completed** | All questions exhausted | Same as admin end session |

### 7.3 Lobby Sub-States

```
Lobby
  ├── LobbyOpen    → new participants may join
  └── LobbyClosed  → no new joins; existing participants retained
```

Admin may toggle lobby sub-state without changing the parent Lobby state.

### 7.4 Architectural Constraints

| Constraint | Enforcement |
|------------|-------------|
| Single active room per admin (v1) | Room Service checks no other room in Setup/Lobby/Active/Paused/SectionBreak before creating new room |
| Room code expiry on Closed | Room code lookup rejects Closed rooms; codes marked expired in database |
| Persist before Completed | Unit of Work commits all responses and scores before state transition |
| Quiz InUse lock | Quiz Service marks quiz InUse on room creation; restores Ready on room Closed |

---

## 8. Quiz Lifecycle

Quiz lifecycle implements SRS Section 13.2. Quizzes are durable templates independent of live sessions.

### 8.1 State Diagram

```
                    ┌─────────┐
                    │  Draft  │◀── admin: create quiz / duplicate
                    └────┬────┘
                         │ all questions valid
                         ▼
                    ┌─────────┐
          ┌────────│  Ready  │────────┐
          │        └────┬────┘        │
          │ admin:      │ admin:       │ admin:
          │ archive     │ createRoom   │ delete
          ▼             ▼              ▼
     ┌─────────┐  ┌─────────┐   ┌─────────┐
     │ Archived│  │ InUse   │   │ Deleted │
     └────┬────┘  └────┬────┘   └─────────┘
          │ admin:      │ room: closed
          │ restore     │
          └─────▶ Ready ◀┘
```

### 8.2 Validation Gate (Draft → Ready)

The Quiz Service validates before allowing Ready transition:

```
Quiz Validation Checklist
─────────────────────────
□ Quiz has title
□ Quiz has at least one section
□ Each section has at least one question
□ Total questions ≤ 100
□ Every question:
  □ Has prompt content (text, image, or audio as required by type)
  □ Has 2–6 answer options
  □ Has at least one correct answer designated
  □ Has base point value ≥ 1
  □ Has valid media references (if Image/Audio type)
□ Quiz configuration settings are valid
```

Validation failures return structured errors indicating which questions need attention.

### 8.3 Quiz Operations

| Operation | Source State | Target State | Notes |
|-----------|-------------|--------------|-------|
| **Create** | — | Draft | Empty quiz with default configuration |
| **Edit** | Draft, Ready | Draft or Ready | Re-validates on save; Ready → Draft if validation fails |
| **Duplicate** | Any except Deleted | Draft (or Ready if valid) | Deep copy of sections, questions, options, config |
| **Archive** | Ready | Archived | Hidden from active library |
| **Restore** | Archived | Ready | Re-validates before restore |
| **Delete** | Draft, Ready, Archived | Deleted | Blocked if InUse |
| **Preview** | Ready | — | Solo mode; no state change |
| **Create Room** | Ready | InUse (quiz), Setup (room) | Creates session snapshot |

### 8.4 Session Snapshot

When a live room is created, the backend deep-copies the quiz template into a session-scoped structure:

```
Quiz Template                    Session Snapshot
─────────────                   ─────────────────
Quiz (id: Q1)        ──────▶   LiveRoom (quizSnapshot)
  Section (S1)                    SessionSection (S1 snapshot)
    Question (Qn)                 SessionQuestion (Qn snapshot)
      Option (On)                     SessionOption (On snapshot)
```

Snapshot preserves question order, options, correct answers, point values, and quiz configuration at the moment of room creation. The snapshot is immutable for the session duration.

---

## 9. Participant Lifecycle

Participant lifecycle implements SRS Section 13.4. The Participant Service manages state within a room context.

### 9.1 State Diagram

```
┌─────────┐     validate      ┌──────────┐    session start   ┌────────┐
│ Joining │─────────────────▶│ InLobby  │──────────────────▶│ Active │
└─────────┘                   └──────────┘                    └───┬────┘
     ▲                                                            │
     │ rejoin (not banned)                                        │
     │                                                            ▼
┌─────────┐                                                  ┌──────────┐
│ Kicked  │◀─────────────────────────────────────────────────│ Answering│
└────┬────┘                                                  └────┬─────┘
     │ ban                                                          │
     ▼                                              ┌───────────────┼───────────────┐
┌─────────┐                                         ▼               ▼               ▼
│ Banned  │                                    ┌──────────┐    ┌──────────┐    ┌──────────┐
└─────────┘                                    │ Buzzing  │    │ Answered │    │ Waiting  │
                                               └────┬─────┘    └──────────┘    └──────────┘
                                                    │
                                                    ▼
                                               ┌──────────────┐
                                               │ BuzzUnlocked │
                                               └──────────────┘

Active ──disconnect──▶ Disconnected ──reconnect──▶ Reconnecting ──▶ Active
Active ──session end──▶ SessionEnded
```

### 9.2 Join and Reconnection Logic

```
Join Request Received
        │
        ▼
   Room Closed? ──yes──▶ Reject: room expired
        │ no
        ▼
   Email banned? ──yes──▶ Reject: banned
        │ no
        ▼
   Existing participant with same email?
        │
   yes ─┤── Restore participant record
        │    Restore score + streak
        │    Issue new session token
        │    Send RESYNC
        │
   no ──┤── Name taken? ──yes──▶ Reject: duplicate name
        │              no
        │              Create participant record
        │              Issue session token
        ▼
   Broadcast participant:joined to admin
   Set state → InLobby (or Active if session already started)
```

### 9.3 Kick and Ban

| Action | Backend Effect | Participant Effect |
|--------|---------------|-------------------|
| **Kick** | Remove from WebSocket channel; set state Kicked | Client shown removal message; disconnected from room |
| **Kick + Ban** | Above + add email to room ban list | Cannot rejoin same room; rejected on join attempt |
| **Rejoin after kick (no ban)** | Restore via normal reconnection flow | Score and progress preserved |

### 9.4 Participant Data Visibility

| Data | Admin | Participant (self) | Participant (others) | Display |
|------|-------|--------------------|----------------------|---------|
| Display name | Yes | Yes | Yes (leaderboard) | Yes (leaderboard) |
| Email | Yes | Yes | No | No |
| Score / rank | Yes | Yes | Yes (leaderboard) | Yes (leaderboard) |
| Connection status | Yes | No | No | No |
| Current activity state | Yes | No | No | No |
| Answer selections | Yes (after submit) | Yes (own) | No | No |

---

## 10. File Upload Architecture

Media files (images, audio) and branding assets are stored on the local filesystem in v1, accessed through an abstracted storage service.

### 10.1 Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FileStorageService                        │
│                    (abstract interface)                      │
│                                                             │
│  upload(file, category) → storedFileReference               │
│  getUrl(storedFileReference) → publicUrl                    │
│  delete(storedFileReference) → void                         │
│  validate(file, category) → pass | reject                     │
└────────────────────────┬────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐
│  LocalStorageBackend │   │  CloudStorageBackend │
│  (v1 — active)       │   │  (future — stub)     │
│                      │   │                      │
│  Render persistent   │   │  S3 / R2 / GCS       │
│  disk volume         │   │                      │
└─────────────────────┘   └─────────────────────┘
```

### 10.2 File Categories and Limits

| Category | Formats | Max Size | Usage |
|----------|---------|----------|-------|
| **Question image** | JPEG, PNG, WebP | 5 MB | Image question prompts |
| **Question audio** | MP3, WAV | 15 MB | Audio question prompts |
| **Quiz branding** | JPEG, PNG, WebP | 2 MB | Per-quiz logo on Presentation Screen |
| **Platform branding** | JPEG, PNG, WebP | 2 MB | Default platform logo |

### 10.3 Upload Flow

```
Admin selects file in Quiz Editor
        │
        ▼
Client-side pre-validation (type, size via Zod)
        │
        ▼
POST multipart upload to backend (admin JWT required)
        │
        ▼
Backend FileStorageService:
  1. Validate MIME type (magic bytes, not just extension)
  2. Validate file size
  3. Generate unique storage key (UUID-based path)
  4. Write to local storage
  5. Persist file metadata record in database
  6. Return file reference (ID + URL)
        │
        ▼
Question record updated with file reference ID
```

### 10.4 Storage Directory Layout (Local)

```
storage/
├── images/
│   └── {uuid}.{ext}
├── audio/
│   └── {uuid}.{ext}
└── branding/
    ├── platform/
    │   └── {uuid}.{ext}
    └── quizzes/
        └── {quizId}/
            └── {uuid}.{ext}
```

### 10.5 File Serving

| Approach | Description |
|----------|-------------|
| **v1** | Backend serves files via a dedicated static/media route; Render persistent disk holds files |
| **Future** | Cloud storage with CDN URL; backend returns signed URLs; upload goes directly to cloud via presigned URL |

### 10.6 File Lifecycle

| Event | Action |
|-------|--------|
| **Question deleted** | Orphan check; delete file if no other references |
| **Quiz deleted** | Delete all associated media files and branding |
| **Replace media** | Delete old file after new file successfully stored |
| **Session snapshot** | Snapshot stores file reference IDs, not copies of files |

---

## 11. API Design Principles

Detailed endpoint definitions are deferred to the API specification phase. This section establishes the architectural principles governing REST API design.

### 11.1 REST Conventions

| Principle | Standard |
|-----------|----------|
| **Base path** | `/api/v1/` prefix for all REST endpoints |
| **Resource naming** | Plural nouns, kebab-case: `/quizzes`, `/live-rooms`, `/session-history` |
| **HTTP methods** | GET (read), POST (create/action), PUT/PATCH (update), DELETE (remove) |
| **Status codes** | 200/201 success, 400 validation, 401 unauthorized, 403 forbidden, 404 not found, 409 conflict, 422 business rule violation, 429 rate limited, 500 server error |
| **Response envelope** | Consistent JSON structure with `data`, `error`, and `meta` fields |
| **Pagination** | Cursor or offset pagination for list endpoints (quiz library, session history) |
| **Filtering** | Query parameters for search, status filter, date range |

### 11.2 Resource Groups (Conceptual)

| Group | Purpose | Auth |
|-------|---------|------|
| **Auth** | Admin login, logout | Public (login) / JWT (logout) |
| **Quizzes** | Quiz CRUD, archive, duplicate, validate | JWT |
| **Questions** | Question CRUD within quizzes, reorder | JWT |
| **Sections** | Section CRUD within quizzes, reorder | JWT |
| **Media** | File upload, delete | JWT |
| **Live Rooms** | Room creation, control actions, QR/link generation | JWT |
| **Join** | Participant join validation, session token issuance | Public (rate limited) |
| **Session History** | Browse past sessions, view results | JWT |
| **Export** | Trigger and download CSV/Excel exports | JWT |
| **Settings** | Platform branding, configuration | JWT |
| **Health** | Health check probe | Public |

### 11.3 WebSocket Protocol Principles

| Principle | Standard |
|-----------|----------|
| **Endpoint** | Single WebSocket endpoint per client type or unified with role identified on connect |
| **Message format** | JSON with `type`, `payload`, and `timestamp` fields |
| **Authentication** | Token passed as query parameter on connect |
| **Acknowledgment** | Critical client actions (submit answer, buzz) receive acknowledgment messages |
| **Error messages** | Structured error events with code and human-readable message |
| **Versioning** | Protocol version included in connect handshake for future compatibility |

### 11.4 Validation Strategy

| Layer | Tool | Responsibility |
|-------|------|----------------|
| **Frontend forms** | Zod + React Hook Form | Immediate user feedback, input shape validation |
| **Frontend API calls** | Zod | Response shape validation for type safety |
| **Backend input** | Pydantic | Request body, query param, and path param validation |
| **Backend business rules** | Service layer | State transition validity, uniqueness checks, authorization |

### 11.5 Idempotency

| Operation | Idempotent | Notes |
|-----------|------------|-------|
| **Submit answer** | Yes | Duplicate submit for same question ignored |
| **Buzz** | Yes | Only first buzz processed; subsequent rejected |
| **Admin state transitions** | Conditional | Invalid transitions rejected without side effect |
| **Join** | Conditional | Same email reconnects rather than creating duplicate |
| **Export** | Yes | Same data produces same export; new file each request |

---

## 12. Database Relationships

Entity relationships are described conceptually. Detailed table schemas are deferred to the database design phase.

### 12.1 Entity Relationship Overview

```
┌──────────────┐
│    Admin      │
└──────────────┘
       │
       │ creates/manages
       ▼
┌──────────────┐       ┌──────────────┐
│    Quiz       │──1:N──│   Section     │
└──────┬───────┘       └──────┬───────┘
       │                      │
       │ 1:N                  │ 1:N
       ▼                      ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│ QuizConfig    │       │   Question    │──1:N──│ AnswerOption  │
└──────────────┘       └──────┬───────┘       └──────────────┘
                              │
                              │ N:1 (optional)
                              ▼
                       ┌──────────────┐
                       │  MediaFile    │
                       └──────────────┘

┌──────────────┐
│    Quiz       │──1:N──┌──────────────┐
└──────────────┘       │  LiveRoom     │
                       └──────┬───────┘
                              │
              ┌───────────────┼───────────────┐
              │ 1:N           │ 1:N           │ 1:1
              ▼               ▼               ▼
       ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
       │ Participant   │ │ SessionQuestion│ │ RoomConfig    │
       └──────┬───────┘ └──────┬───────┘ └──────────────┘
              │                │
              │ 1:N            │ 1:N
              ▼                ▼
       ┌──────────────┐ ┌──────────────┐
       │  Response     │ │ SessionOption │
       └──────────────┘ └──────────────┘

┌──────────────┐
│ SecurityLog   │  (standalone audit trail)
└──────────────┘
```

### 12.2 Relationship Summary

| Parent | Child | Cardinality | Description |
|--------|-------|-------------|-------------|
| Quiz | Section | 1:N | Quiz contains ordered sections |
| Section | Question | 1:N | Section contains ordered questions |
| Question | AnswerOption | 1:N | Question has 2–6 options |
| Question | MediaFile | N:1 | Optional media attachment |
| Quiz | QuizConfig | 1:1 | Scoring and behavior settings |
| Quiz | LiveRoom | 1:N | Quiz used in multiple sessions over time |
| LiveRoom | Participant | 1:N | Room has many participants |
| LiveRoom | SessionQuestion | 1:N | Immutable snapshot of questions for this session |
| SessionQuestion | SessionOption | 1:N | Immutable snapshot of options |
| Participant | Response | 1:N | One response per question per participant |
| LiveRoom | RoomConfig | 1:1 | Snapshot of quiz config for this session |
| Quiz | MediaFile | 1:N | Branding assets |

### 12.3 Key Uniqueness Constraints (Conceptual)

| Scope | Fields | Purpose |
|-------|--------|---------|
| LiveRoom | roomCode (while active) | Join lookup |
| LiveRoom | secretToken (while active) | Display access |
| Participant (per room) | displayName | SRS FR-064 |
| Participant (per room) | email | SRS FR-063 |
| MediaFile | storageKey | File system path uniqueness |

### 12.4 Soft Delete vs. Hard Delete

| Entity | Delete Strategy |
|--------|----------------|
| **Quiz** | Soft delete (Deleted state) with hard delete option; blocked when InUse |
| **Session history** | Hard delete (admin-initiated, individual or bulk) |
| **Media files** | Hard delete from storage + database |
| **Participant data** | Hard delete cascades with session deletion |

---

## 13. Error Handling Strategy

### 13.1 Error Classification

| Category | HTTP Code | WebSocket Code | Example |
|----------|-----------|----------------|---------|
| **Validation error** | 400 / 422 | `VALIDATION_ERROR` | Missing required field, invalid email format |
| **Authentication error** | 401 | `AUTH_ERROR` | Expired JWT, invalid session token |
| **Authorization error** | 403 | `FORBIDDEN` | Participant attempting admin action |
| **Not found** | 404 | `NOT_FOUND` | Invalid room code, deleted quiz |
| **Conflict** | 409 | `CONFLICT` | Duplicate name/email, quiz InUse on delete |
| **Rate limited** | 429 | — | Too many login or join attempts |
| **Business rule violation** | 422 | `BUSINESS_RULE` | Invalid state transition, buzz after lock |
| **Server error** | 500 | `INTERNAL_ERROR` | Unexpected failure |

### 13.2 Error Response Structure (REST)

All REST error responses follow a consistent envelope:

```
{
  "error": {
    "code": "DUPLICATE_DISPLAY_NAME",
    "message": "Human-readable description for UI display",
    "details": [ ... optional field-level errors ... ]
  },
  "meta": {
    "requestId": "correlation-id"
  }
}
```

### 13.3 Frontend Error Handling

| Layer | Behavior |
|-------|----------|
| **Axios interceptor** | Normalize error envelope; redirect to login on 401 (admin) |
| **TanStack Query** | Global error handler for query/mutation failures; toast notifications |
| **React Hook Form** | Map server field errors to form field `errors` |
| **WebSocket handler** | Display inline error for action failures (buzz rejected, submit failed) |
| **Error boundaries** | Catch render errors per module; show recovery UI |

### 13.4 Backend Error Handling

| Layer | Behavior |
|-------|----------|
| **Pydantic validation** | Auto-return 422 with field details |
| **Service layer** | Raise typed domain exceptions (e.g., `RoomNotFound`, `InvalidTransition`) |
| **Exception handler middleware** | Catch domain exceptions → map to HTTP/WS error codes |
| **Unexpected exceptions** | Log full traceback with request ID; return generic 500 to client |
| **WebSocket errors** | Send error event to initiating client; do not broadcast |

### 13.5 Logging on Error

| Severity | Condition | Action |
|----------|-----------|--------|
| **WARN** | Business rule violation, validation failure | Log with request ID and context |
| **ERROR** | Unexpected exception, database failure | Log full traceback with request ID |
| **INFO** | Security event (failed login) | Log to security audit trail |
| **Never** | — | Log passwords, JWT tokens, or participant emails in error logs |

---

## 14. Security Considerations

### 14.1 Security Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                         │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Transport: HTTPS everywhere (Vercel + Render TLS)     │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Authentication: JWT (admin) | session token (join)  │  │
│  │                  | secret link (display)             │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Authorization: Role-based guards on all endpoints    │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Input Validation: Pydantic + Zod + file magic bytes  │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Rate Limiting: Login + join endpoints                │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Data Protection: Password hashing, email restricted  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 14.2 Authentication Security

| Measure | Implementation |
|---------|---------------|
| **Password storage** | bcrypt or argon2 one-way hashing; never store plaintext |
| **Password policy** | Minimum 12 characters with complexity requirements (FR-005) |
| **JWT signing** | HS256 or RS256 with secret stored in environment variable |
| **JWT expiry** | ~8 hours; no refresh token in v1; client redirects to login on expiry |
| **Session token entropy** | Cryptographically random, sufficient length to prevent guessing |
| **Secret link entropy** | Cryptographically random token for Presentation Screen access |
| **Room code entropy** | 6-character alphanumeric from secure random source (~2 billion combinations) |

### 14.3 Authorization Rules

| Resource | Admin | Participant | Display |
|----------|-------|-------------|---------|
| Quiz CRUD | Full | None | None |
| Live room control | Full | None | None |
| Join room | None | Own room only | None |
| Submit answer / buzz | None | Own responses only | None |
| View participant emails | Yes | Own only | None |
| View leaderboard | Yes | Yes (always) | Yes (always) |
| Export data | Yes | None | None |
| View session history | Yes | None | None |

### 14.4 Input and File Security

| Threat | Mitigation |
|--------|------------|
| **SQL injection** | SQLAlchemy parameterized queries exclusively |
| **XSS** | React auto-escaping; sanitize any rich text if introduced later |
| **CSRF** | JWT in Authorization header (not cookies) eliminates CSRF for admin |
| **Malicious file upload** | MIME validation via magic bytes; size limits; stored outside web root |
| **Path traversal** | UUID-based storage keys; no user-supplied paths |
| **Room code brute force** | Rate limiting on join endpoint; codes expire on session close |

### 14.5 CORS and Headers

| Header | Value |
|--------|-------|
| **Access-Control-Allow-Origin** | Vercel frontend domain only |
| **X-Content-Type-Options** | nosniff |
| **X-Frame-Options** | DENY (except Display may use same origin) |
| **Strict-Transport-Security** | max-age configured on Render |

### 14.6 Secrets Management

| Secret | Storage |
|--------|---------|
| **JWT signing key** | Render environment variable |
| **Database URL** | Render environment variable (Neon connection string) |
| **Admin password hash** | Database (seeded at deploy) |
| **Never in source control** | All secrets via environment variables |

---

## 15. Scalability Considerations

### 15.1 v1 Capacity Targets

| Dimension | Target | Source |
|-----------|--------|--------|
| Concurrent live rooms | 5 | NFR-031 |
| Participants per room | 100 | NFR-031 |
| Real-time event latency | ≤ 1 second (P95) | NFR-001 |
| Questions per quiz | 100 | FR-017 |
| Quiz library size | Unlimited | FR-018 |

### 15.2 Scaling Strategy by Tier

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (Vercel)                                          │
│  ─────────────────                                          │
│  Scales automatically via CDN + serverless functions         │
│  Static assets edge-cached globally                          │
│  No scaling action required for v1 targets                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  BACKEND (Render)                                           │
│  ─────────────────                                          │
│  v1: Single instance (modular monolith)                     │
│  Vertical scaling: upgrade Render plan for more CPU/RAM      │
│  Future: Multiple instances + sticky sessions for WebSocket  │
│          OR dedicated WebSocket service                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  DATABASE (Neon)                                            │
│  ─────────────────                                          │
│  Serverless PostgreSQL with auto-scaling compute             │
│  Connection pooling via Neon's built-in pooler               │
│  Future: Read replicas for session history queries           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  FILE STORAGE                                               │
│  ─────────────────                                          │
│  v1: Render persistent disk (single instance bound)          │
│  Future: Cloud storage (S3/R2) decouples from compute        │
└─────────────────────────────────────────────────────────────┘
```

### 15.3 Backend Performance Optimizations

| Optimization | Purpose |
|--------------|---------|
| **In-memory room context** | Avoid database reads on every WebSocket event |
| **Room-scoped broadcast** | O(participants in room) not O(all users) |
| **Batch leaderboard computation** | Compute once per scored question, broadcast to all |
| **Connection pooling** | SQLAlchemy pool against Neon pooler |
| **Async I/O** | FastAPI async endpoints for concurrent request handling |
| **Lazy export generation** | Exports built on demand, not pre-computed |

### 15.4 Known v1 Limitations

| Limitation | Impact | Future Mitigation |
|------------|--------|-------------------|
| Single backend instance | WebSocket state in process memory; no failover mid-session | Redis-backed room state + sticky sessions |
| Local file storage on Render disk | Files lost if disk not persisted or instance replaced | Cloud storage migration |
| Single admin host | Only one actively controlled room | Multi-admin architecture |
| No horizontal WebSocket scaling | 5 rooms × 100 participants on one process | Dedicated real-time service |

### 15.5 Growth Path

```
Phase 1 (v1):  Modular monolith on Render + Neon + Vercel
                  │
Phase 2:       Cloud file storage (S3/R2)
                  │
Phase 3:       Redis for room runtime state + session store
                  │
Phase 4:       Separate WebSocket service (horizontal scaling)
                  │
Phase 5:       Multi-admin, multi-tenant architecture
```

---

## 16. Folder Structure

### 16.1 Monorepo Layout

```
QuizArena/
├── docs/
│   ├── PROJECT_SPEC.md              # Software Requirements Specification
│   └── SYSTEM_ARCHITECTURE.md         # This document
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── app/                       # App shell, providers, router
│   │   ├── modules/
│   │   │   ├── admin/                 # Admin Dashboard module
│   │   │   ├── join/                  # Participant Client module
│   │   │   └── display/               # Presentation Screen module
│   │   ├── shared/
│   │   │   ├── components/            # Reusable UI components
│   │   │   ├── hooks/                 # Shared React hooks
│   │   │   ├── lib/                   # Axios client, WebSocket client, utils
│   │   │   ├── schemas/               # Zod validation schemas
│   │   │   └── types/                 # Shared TypeScript types
│   │   └── styles/                    # Tailwind config, global styles
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI application entry point
│   │   ├── config.py                  # Environment configuration
│   │   ├── api/
│   │   │   ├── deps.py                # Dependency injection (auth, db session)
│   │   │   ├── routers/               # REST route handlers by domain
│   │   │   └── websocket/             # WebSocket connection handlers
│   │   ├── core/
│   │   │   ├── security.py            # JWT, password hashing, token utils
│   │   │   ├── exceptions.py          # Domain exception classes
│   │   │   └── middleware.py          # CORS, rate limiting, error handler
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── services/                  # Business logic layer
│   │   │   ├── auth_service.py
│   │   │   ├── quiz_service.py
│   │   │   ├── question_service.py
│   │   │   ├── room_service.py
│   │   │   ├── participant_service.py
│   │   │   ├── scoring_service.py
│   │   │   ├── leaderboard_service.py
│   │   │   ├── export_service.py
│   │   │   ├── file_storage_service.py
│   │   │   ├── timer_service.py
│   │   │   └── state_machine/         # Room, quiz, question, participant FSMs
│   │   ├── repositories/              # Data access layer
│   │   └── storage/                   # File storage backends
│   │       ├── base.py                # Abstract storage interface
│   │       ├── local.py               # Local filesystem backend
│   │       └── cloud.py               # Future cloud backend (stub)
│   ├── alembic/                       # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── scripts/
│   │   └── seed_admin.py              # Admin account seeding
│   ├── requirements.txt
│   └── alembic.ini
│
├── storage/                           # Local file storage (dev only; prod on Render disk)
│   ├── images/
│   ├── audio/
│   └── branding/
│
├── .gitignore
└── README.md
```

### 16.2 Frontend Module Internal Structure

Each client module follows a consistent internal layout:

```
modules/admin/
├── pages/                 # Route-level page components
├── components/            # Module-specific components
├── hooks/                 # Module-specific hooks (e.g., useLiveRoom)
├── layouts/               # Admin layout with sidebar
└── index.ts               # Module route definitions

modules/join/
├── pages/                 # Join, lobby, gameplay pages
├── components/            # Question display, buzzer, leaderboard
├── hooks/                 # useParticipantSession, useReconnect
└── index.ts

modules/display/
├── pages/                 # Display page (full-screen)
├── components/            # Podium, section leaderboard, question display
├── hooks/                 # useDisplaySession
└── index.ts
```

### 16.3 Backend Service Layer Organization

```
services/
├── state_machine/
│   ├── room_fsm.py        # Room state transitions (SRS 13.1)
│   ├── quiz_fsm.py        # Quiz state transitions (SRS 13.2)
│   ├── question_fsm.py    # Question live states (SRS 13.3)
│   └── participant_fsm.py # Participant states (SRS 13.4)
├── scoring_service.py     # Implements SRS Section 12 rules
├── leaderboard_service.py # Ranking with tie-breaking (SR-040–SR-044)
└── ...
```

---

## 17. Technology Decisions

### 17.1 Technology Decision Records

| Decision | Choice | Alternatives Considered | Rationale |
|----------|--------|------------------------|-----------|
| **Frontend framework** | React 18+ | Vue, Svelte | SRS mandate; largest ecosystem; team familiarity |
| **Language** | TypeScript | JavaScript | Type safety across three clients and shared schemas |
| **Styling** | Tailwind CSS | CSS Modules, Styled Components | SRS mandate; rapid responsive UI; consistent design tokens |
| **Routing** | React Router v6 | TanStack Router | Mature; supports nested layouts for three client modules |
| **Server state** | TanStack Query | Redux, SWR | Optimized for REST CRUD; cache invalidation; minimal boilerplate |
| **HTTP client** | Axios | fetch, ky | Interceptor support for JWT; wide adoption |
| **Forms** | React Hook Form | Formik | Performance (uncontrolled inputs); Zod integration |
| **Validation** | Zod | Yup, Joi | TypeScript-first; shared between forms and API parsing |
| **Backend framework** | FastAPI | Django, Flask | SRS mandate; async support; automatic OpenAPI docs; WebSocket support |
| **ORM** | SQLAlchemy 2.0 | Tortoise ORM, raw SQL | Mature; supports SQLite and PostgreSQL; Alembic integration |
| **Migrations** | Alembic | Manual SQL | Standard SQLAlchemy migration tool; version-controlled schema |
| **Auth** | PyJWT + bcrypt | Auth0, custom sessions | SRS mandate for JWT; single admin avoids OAuth complexity in v1 |
| **Real-time** | Native WebSockets | Socket.IO, SSE | FastAPI native support; lighter dependency; SRS allows WebSockets |
| **Database (prod)** | Neon PostgreSQL | Supabase, Railway PG | Serverless-compatible; scales with usage; free tier for development |
| **Database (dev)** | SQLite | Docker PostgreSQL | Zero setup; fast iteration; SQLAlchemy compatibility |
| **File storage** | Local disk + abstract interface | S3 direct | Simplicity for v1; interface enables future cloud migration |
| **Frontend hosting** | Vercel | Netlify, Cloudflare Pages | Optimized for React SPAs; automatic HTTPS; edge CDN |
| **Backend hosting** | Render | Railway, Fly.io | Persistent disk for file storage; straightforward deploy; WebSocket support |
| **Export format** | openpyxl + csv stdlib | Pandas | Lightweight; no heavy data processing dependency |

### 17.2 Key Trade-offs

| Trade-off | Decision | Accepted Cost |
|-----------|----------|---------------|
| **Monolith vs. microservices** | Modular monolith | Single deploy unit; future extraction possible via module boundaries |
| **Socket.IO vs. native WebSocket** | Native WebSocket | Manual reconnection logic; simpler stack; no Socket.IO protocol overhead |
| **In-memory room state vs. Redis** | In-memory for v1 | Session lost on backend restart; acceptable per best-effort availability |
| **Local storage vs. cloud** | Local for v1 | Files tied to Render instance; mitigated by storage abstraction layer |
| **Single SPA vs. three apps** | Single SPA with route modules | Larger bundle; mitigated by code splitting per module |
| **Server-authoritative timer vs. client timer** | Server-authoritative | Slight display lag on timer; guarantees fairness and consistency |

### 17.3 Dependency on SRS Requirements

| SRS Requirement | Architectural Decision |
|-----------------|----------------------|
| FR-091 (leaderboard always on) | Leaderboard broadcast hardcoded in scoring pipeline; no feature flag |
| ASM-007 (server timers) | Timer Service with async backend scheduling; clients display only |
| SR-001–SR-044 (scoring rules) | Dedicated ScoringService module; pure functions for testability |
| RS-003 (single active room) | Room Service enforces constraint at creation time |
| NFR-061 (SQLite dev / PG prod) | SQLAlchemy + DATABASE_URL environment variable |
| CON-005 (open-source only) | All selected technologies are open-source |

---

## 18. Deployment Architecture

### 18.1 Production Environment Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PRODUCTION ENVIRONMENT                          │
│                                                                         │
│  ┌─────────────────────┐                                                │
│  │       Vercel         │                                                │
│  │  ┌───────────────┐  │         HTTPS/WSS                               │
│  │  │  React SPA     │──┼─────────────────────────┐                      │
│  │  │  (static CDN)  │  │                         │                      │
│  │  └───────────────┘  │                         ▼                      │
│  └─────────────────────┘              ┌─────────────────────┐           │
│                                       │       Render         │           │
│                                       │  ┌───────────────┐  │           │
│                                       │  │  FastAPI App   │  │           │
│                                       │  │  REST + WS     │  │           │
│                                       │  └───────┬───────┘  │           │
│                                       │          │          │           │
│                                       │  ┌───────▼───────┐  │           │
│                                       │  │ Persistent Disk│  │           │
│                                       │  │  /storage/     │  │           │
│                                       │  └───────────────┘  │           │
│                                       └──────────┬──────────┘           │
│                                                  │                      │
│                                       ┌──────────▼──────────┐           │
│                                       │    Neon PostgreSQL   │           │
│                                       │    (serverless)      │           │
│                                       └─────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 18.2 Environment Configuration

| Environment | Frontend | Backend | Database | Storage |
|-------------|----------|---------|----------|---------|
| **Local dev** | Vite dev server (localhost:5173) | Uvicorn (localhost:8000) | SQLite file | `./storage/` local directory |
| **Production** | Vercel (app.quizarena.com) | Render (api.quizarena.com) | Neon PostgreSQL | Render persistent disk `/storage/` |

### 18.3 Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | Backend | SQLAlchemy connection string (SQLite or Neon) |
| `JWT_SECRET_KEY` | Backend | JWT signing secret |
| `JWT_EXPIRY_HOURS` | Backend | Token lifetime (default: 8) |
| `ADMIN_USERNAME` | Backend | Seed admin username (deploy-time) |
| `ADMIN_PASSWORD_HASH` | Backend | Pre-hashed admin password (deploy-time) |
| `CORS_ORIGINS` | Backend | Allowed frontend origin(s) |
| `STORAGE_BACKEND` | Backend | `local` (v1) or `cloud` (future) |
| `STORAGE_PATH` | Backend | Local storage root path |
| `VITE_API_BASE_URL` | Frontend | Backend REST API base URL |
| `VITE_WS_BASE_URL` | Frontend | Backend WebSocket base URL |

### 18.4 Deployment Pipeline

```
┌─────────────── DEVELOPMENT ───────────────┐
│  Local machine                             │
│  frontend: npm run dev                     │
│  backend:  uvicorn app.main:app --reload   │
│  db:       SQLite + alembic upgrade head   │
│  seed:     python scripts/seed_admin.py    │
└────────────────────────────────────────────┘

┌─────────────── PRODUCTION ────────────────┐
│                                           │
│  Git push to main                         │
│       │                                   │
│       ├──────────────────┐                │
│       ▼                  ▼                │
│  Vercel (auto)     Render (auto)          │
│  ├─ npm build      ├─ pip install         │
│  ├─ deploy CDN     ├─ alembic upgrade head│
│  └─ live           ├─ seed admin (if new) │
│                    └─ uvicorn start       │
│                                           │
└───────────────────────────────────────────┘
```

### 18.5 Domain and Routing

| Domain | Target | Purpose |
|--------|--------|---------|
| `app.quizarena.com` | Vercel | Frontend SPA (all three clients) |
| `api.quizarena.com` | Render | Backend REST + WebSocket |

Frontend routes handle client separation:

```
app.quizarena.com/admin/*          → Admin Dashboard
app.quizarena.com/join/*           → Participant Client
app.quizarena.com/display/:token   → Presentation Screen
```

QR codes encode: `https://app.quizarena.com/join/{roomCode}`

### 18.6 Health Check and Monitoring

| Component | Mechanism |
|-----------|-----------|
| **Backend health** | `GET /api/v1/health` returns status + database connectivity check |
| **Render health check** | Configured to probe health endpoint; restart on failure |
| **Vercel** | Automatic deployment status monitoring |
| **Neon** | Built-in database monitoring dashboard |
| **Logging** | Structured JSON logs on Render; stdout captured by Render log stream |
| **Security events** | Login/logout/failed auth persisted to SecurityLog table |

### 18.7 Deployment Constraints and Notes

| Constraint | Mitigation |
|------------|------------|
| Render free/starter tier sleep | Use paid Render plan for live events; health check ping to prevent sleep |
| Render persistent disk size | Monitor disk usage; implement file cleanup for orphaned media |
| Neon connection limits | Use Neon connection pooler; configure SQLAlchemy pool size |
| WebSocket on Render | Render supports WebSocket on paid plans; verify proxy timeout settings |
| Vercel environment variables | Set `VITE_*` vars in Vercel dashboard per environment |
| No CI/CD in v1 scope | Manual git-push deploy; future: GitHub Actions for tests before deploy |

---

## Document References

| Document | Relationship |
|----------|-------------|
| [PROJECT_SPEC.md](./PROJECT_SPEC.md) | Requirements baseline — defines **what** the system must do |
| **This document** | Architecture baseline — defines **how** the system is structured |
| API Specification (planned) | Will define REST endpoints and WebSocket event schemas |
| Database Schema (planned) | Will define tables, columns, indexes, and constraints |

---

*End of Document*
