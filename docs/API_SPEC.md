# QuizArena — API Specification

| Field | Value |
|-------|-------|
| **Document Title** | QuizArena — API Specification |
| **Version** | 1.0 |
| **Status** | Draft for Review |
| **Date** | July 31, 2026 |
| **Prepared By** | Software Architecture Team |
| **Architecture Baseline** | [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) v1.0 |
| **Requirements Baseline** | [PROJECT_SPEC.md](./PROJECT_SPEC.md) v1.1 |
| **Related** | [SOCKET_EVENTS.md](./SOCKET_EVENTS.md), [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Conventions](#2-conventions)
3. [Authentication](#3-authentication)
4. [Error Handling](#4-error-handling)
5. [Idempotency](#5-idempotency)
6. [Resource Groups](#6-resource-groups)
7. [Auth](#7-auth)
8. [Quizzes](#8-quizzes)
9. [Sections and Questions](#9-sections-and-questions)
10. [Media](#10-media)
11. [Live Rooms](#11-live-rooms)
12. [Join](#12-join)
13. [Session History and Export](#13-session-history-and-export)
14. [Settings](#14-settings)
15. [Health](#15-health)
16. [WebSocket Entry](#16-websocket-entry)
17. [Validation Strategy](#17-validation-strategy)
18. [Open Items](#18-open-items)

---

## 1. Overview

QuizArena exposes a versioned HTTPS REST API under `/api/v1/` for transactional operations (CRUD, authentication, uploads, exports, join validation). Live session synchronization uses **native WebSockets** (not Socket.IO); see [SOCKET_EVENTS.md](./SOCKET_EVENTS.md).

This specification follows architecture §11. Exact path shapes below use the documented naming conventions (plural nouns, kebab-case) and the operations owned by each service module. Where architecture names a concrete path (e.g. login, health), that path is authoritative.

| Item | Value |
|------|-------|
| Local base | `http://localhost:8000` |
| Production base | `https://api.quizarena.com` |
| API prefix | `/api/v1/` |
| Content-Type | `application/json` (except multipart media upload) |

---

## 2. Conventions

| Principle | Standard |
|-----------|----------|
| **Base path** | `/api/v1/` for all REST endpoints |
| **Resource naming** | Plural nouns, kebab-case: `/quizzes`, `/live-rooms`, `/session-history` |
| **HTTP methods** | GET (read), POST (create/action), PUT/PATCH (update), DELETE (remove) |
| **Status codes** | 200/201 success; 400 validation; 401 unauthorized; 403 forbidden; 404 not found; 409 conflict; 422 business rule violation; 429 rate limited; 500 server error |
| **Response envelope** | Consistent JSON with `data`, `error`, and `meta` fields |
| **Pagination** | Cursor or offset for list endpoints (quiz library, session history) |
| **Filtering** | Query parameters for search, status filter, date range |

Success responses place the payload under `data` and optional metadata under `meta` (e.g. `requestId`, pagination cursors).

---

## 3. Authentication

Two REST-relevant auth models plus display secret for WebSocket/snapshot access:

| Client | Mechanism | REST usage |
|--------|-----------|------------|
| **Admin** | JWT Bearer (~8 hours, no refresh in v1) | `Authorization: Bearer <JWT>` on protected routes |
| **Participant** | Room-scoped session token | Header or query param on participant REST actions |
| **Presentation** | Secret link token | Validates mapping to active room; read-only snapshot / WS |

### 3.1 Administrator login (concrete)

```
POST /admin/login
Body: { username, password }
→ 200 { accessToken, expiresAt }
```

Subsequent admin requests use `Authorization: Bearer <JWT>`.

JWT conceptual claims: `sub` (admin id), `iat`, `exp`, `role` = `admin`.

```
POST /admin/logout
→ logs security event; client discards token
```

Login (and join) endpoints are rate-limited (NFR-023).

### 3.2 Authorization matrix (REST-relevant)

| Resource | Admin | Participant | Display |
|----------|-------|-------------|---------|
| Quiz CRUD | Full | None | None |
| Live room control | Full | None | None |
| Join room | None | Own join flow | None |
| Submit answer / buzz | None | Own responses only (primarily WS) | None |
| View participant emails | Yes | Own only | None |
| View leaderboard | Yes | Yes | Yes |
| Export / session history | Yes | None | None |

---

## 4. Error Handling

### 4.1 Classification

| Category | HTTP | Example |
|----------|------|---------|
| Validation | 400 / 422 | Missing field, invalid email |
| Authentication | 401 | Expired JWT, invalid session token |
| Authorization | 403 | Participant attempting admin action |
| Not found | 404 | Invalid room code, deleted quiz |
| Conflict | 409 | Duplicate name/email, quiz InUse on delete |
| Rate limited | 429 | Too many login or join attempts |
| Business rule | 422 | Invalid state transition |
| Server error | 500 | Unexpected failure |

### 4.2 Error envelope

```json
{
  "error": {
    "code": "DUPLICATE_DISPLAY_NAME",
    "message": "Human-readable description for UI display",
    "details": []
  },
  "meta": {
    "requestId": "correlation-id"
  }
}
```

---

## 5. Idempotency

| Operation | Idempotent | Notes |
|-----------|------------|-------|
| Submit answer | Yes | Duplicate submit for same question ignored |
| Buzz | Yes | Only first buzz processed; subsequent rejected |
| Admin state transitions | Conditional | Invalid transitions rejected without side effect |
| Join | Conditional | Same email reconnects rather than creating duplicate |
| Export | Yes | Same data produces same export; new file each request |

---

## 6. Resource Groups

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

---

## 7. Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/admin/login` | Public | Issue admin JWT; log security event |
| `POST` | `/admin/logout` | JWT | Log security event; client discards token |

Password policy: minimum 12 characters with complexity requirements (FR-005). Passwords verified against stored hash.

---

## 8. Quizzes

Resource base: `/api/v1/quizzes` (kebab-case plural per conventions).

| Operation | Auth | Description |
|-----------|------|-------------|
| List | JWT | Paginated library; filter/search by title/status |
| Create | JWT | Creates quiz in Draft with default configuration |
| Get | JWT | Quiz detail including sections/questions as needed |
| Update | JWT | Edit; re-validates on save; Ready → Draft if validation fails |
| Delete | JWT | Soft/hard delete per schema rules; blocked if InUse |
| Archive | JWT | Ready → Archived |
| Restore | JWT | Archived → Ready (re-validates) |
| Duplicate | JWT | Deep copy of sections, questions, options, config → Draft (or Ready if valid) |
| Validate | JWT | Run Draft → Ready validation checklist |
| Preview | JWT | Solo preview mode; no quiz state change (Ready) |

**Ready validation checklist (must fail with structured field errors):**

- Quiz has title
- At least one section; each section ≥ 1 question; total questions ≤ 100
- Every question: prompt content; 2–6 options; ≥ 1 correct; base points ≥ 1; valid media refs if Image/Audio
- Quiz configuration settings valid

---

## 9. Sections and Questions

Nested under quizzes (architecture: Sections and Questions resource groups).

| Group | Operations | Auth |
|-------|------------|------|
| **Sections** | CRUD within quiz; reorder | JWT |
| **Questions** | CRUD within quiz/section; reorder; attach media reference | JWT |

Question grading model for live play is all-or-nothing multiple-choice comparison on the server (architecture scoring pipeline). Buzzer eligibility is enforced server-side during live sessions.

---

## 10. Media

| Operation | Auth | Description |
|-----------|------|-------------|
| Upload | JWT | `multipart/form-data`; validate MIME (magic bytes) and size; persist MediaFile metadata; return file reference (ID + URL) |
| Delete | JWT | Remove metadata + storage object subject to orphan rules |
| Serve | As configured | v1: backend static/media route from local/Render disk |

Upload categories and limits: see [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) §8 / architecture §10.2.

---

## 11. Live Rooms

Resource base: `/api/v1/live-rooms`.

| Operation | Auth | Description |
|-----------|------|-------------|
| Create | JWT | From Ready quiz → quiz InUse, room Setup; create session snapshot; enforce single active room per admin (v1) |
| Get | JWT | Room detail / control snapshot |
| Open lobby | JWT | Setup → Lobby; generate room code, QR target, secret display link; lobby Open |
| Toggle lobby | JWT | LobbyOpen ↔ LobbyClosed without leaving Lobby |
| Start session | JWT | Lobby → Active; first question Pending |
| Pause / resume | JWT | Active ↔ Paused; timer freeze/restore |
| Advance / skip / end | JWT | Host control actions owned by Room Service |
| Close room | JWT | → Closed; expire codes/tokens; release runtime; quiz InUse → Ready |
| Kick / ban | JWT | Participant removal; optional email ban list |

QR codes encode: `https://app.quizarena.com/join/{roomCode}`.  
Display share link: `https://app.quizarena.com/display/{secretToken}`.

Live control may also be issued over WebSocket (architecture §6.3 Admin control); REST and WS both funnel through Room Service state machines.

---

## 12. Join

Public, rate-limited.

| Operation | Auth | Description |
|-----------|------|-------------|
| Join / validate | Public | Submit room code + display name + email |

**Server validation:**

1. Room exists and is not Closed  
2. Lobby open (or reconnection allowed)  
3. Name unique within room  
4. Email unique within room **or** matches existing participant for reconnection  
5. Email not on room ban list  

**Success:** create or restore participant; issue participant session token; client stores token (session storage) for REST and WebSocket handshake.

---

## 13. Session History and Export

| Group | Auth | Description |
|-------|------|-------------|
| **Session History** (`/api/v1/session-history`) | JWT | Browse past sessions; view results; hard delete individual or bulk |
| **Export** | JWT | Trigger CSV and Excel generation from persisted session data; async build with temporary download URL or direct stream |

---

## 14. Settings

| Operation | Auth | Description |
|-----------|------|-------------|
| Platform branding / configuration | JWT | Platform settings and branding defaults (architecture Settings group) |

---

## 15. Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/health` | Public | Status + database connectivity check (Render health probe) |

---

## 16. WebSocket Entry

REST is not used for live question broadcast. Clients open a WebSocket connection (token as query parameter on connect). Protocol message shape, event catalog, and resync behavior: [SOCKET_EVENTS.md](./SOCKET_EVENTS.md).

Architecture allows a single unified WebSocket endpoint with role identified on connect, or one endpoint per client type.

---

## 17. Validation Strategy

| Layer | Tool | Responsibility |
|-------|------|----------------|
| Frontend forms | Zod + React Hook Form | Immediate feedback |
| Frontend API calls | Zod | Response shape validation |
| Backend input | Pydantic | Body, query, path validation |
| Backend business rules | Service layer | Transitions, uniqueness, authorization |

---

## 18. Open Items

Architecture §11 defers fine-grained OpenAPI path lists and request/response field schemas to implementation. Implementations must not add resource groups or capabilities outside this document and SYSTEM_ARCHITECTURE.md. WebSocket event payload schemas belong in [SOCKET_EVENTS.md](./SOCKET_EVENTS.md).

---

*End of Document*
