# QuizArena — UI Flow

| Field | Value |
|-------|-------|
| **Document Title** | QuizArena — UI Flow |
| **Version** | 1.0 |
| **Status** | Draft for Review |
| **Date** | July 31, 2026 |
| **Prepared By** | Software Architecture Team |
| **Architecture Baseline** | [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) v1.0 |
| **Requirements Baseline** | [PROJECT_SPEC.md](./PROJECT_SPEC.md) v1.1 |
| **Related** | [SOCKET_EVENTS.md](./SOCKET_EVENTS.md), [API_SPEC.md](./API_SPEC.md) |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Application Structure](#2-application-structure)
3. [Route Map](#3-route-map)
4. [State Management](#4-state-management)
5. [Admin Dashboard Flows](#5-admin-dashboard-flows)
6. [Participant Client Flows](#6-participant-client-flows)
7. [Presentation Screen Flows](#7-presentation-screen-flows)
8. [Cross-Client Live States](#8-cross-client-live-states)
9. [Shared Frontend Concerns](#9-shared-frontend-concerns)
10. [Open Items](#10-open-items)

---

## 1. Overview

QuizArena is a single React SPA with three route-based client modules sharing one backend:

| Client | Users | Device context |
|--------|-------|----------------|
| **Admin Dashboard** (`/admin/*`) | Quiz administrator | Desktop and mobile browsers |
| **Participant Client** (`/join/*`) | Quiz players | Desktop and mobile browsers |
| **Presentation Screen** (`/display/:secretToken`) | Audience / room display | TVs, projectors, large displays |

Clients are thin renderers: they display server state and capture input. Scores, timers, and state transitions are server-authoritative. Live session UI is driven by WebSocket events; REST (TanStack Query) is used for durable CRUD and history—not for live room state.

---

## 2. Application Structure

```
App Shell (React Router | TanStack Query | Auth Context)
    ├── Admin Module   /admin/*
    ├── Join Module    /join/*
    └── Display Module /display/:token
Shared: UI components | hooks | WebSocket client | Axios | Zod | types
```

Stack (architecture): React + TypeScript + Tailwind CSS; React Router; TanStack Query; Axios; React Hook Form + Zod.

---

## 3. Route Map

| Route | Client | Auth | Description |
|-------|--------|------|-------------|
| `/admin/login` | Admin | None | Administrator login |
| `/admin/*` | Admin | JWT | Quiz management, live hosting, history, exports |
| `/join` | Participant | None | Room code entry |
| `/join/:roomCode` | Participant | None | QR deep-link join |
| `/join/:roomCode/lobby` | Participant | Session token | Waiting lobby |
| `/join/:roomCode/play` | Participant | Session token | Live gameplay |
| `/display/:secretToken` | Presentation | Secret token | Full-screen audience display |

Production hosts: `app.quizarena.com` (SPA). QR encodes `https://app.quizarena.com/join/{roomCode}`. Display share link uses `/display/{secretToken}`.

---

## 4. State Management

| State type | Mechanism | Scope |
|------------|-----------|-------|
| Server data (REST) | TanStack Query | Quizzes, questions, session history, exports |
| Auth state | React Context | JWT, admin session |
| Participant session | Local/session storage + Context | Participant session token, room identity |
| Live session state | WebSocket-driven React state | Room state, current question, timer, leaderboard |
| Form state | React Hook Form + Zod | Quiz editor, question editor, join form, login |
| UI state | Component-local | Modals, toggles, loading indicators |

**Rule:** Live session data is never stored in TanStack Query cache—it flows only through the WebSocket connection into live-session hooks.

---

## 5. Admin Dashboard Flows

### 5.1 Layout

```
Sidebar: Dashboard | Quizzes | History | Settings
Main:    Quiz Library | Quiz Editor | Preview
         Live Room Control | Monitor Panel
         Session Results | Export
```

### 5.2 Authentication

```
/admin/login → POST credentials → store JWT in memory (Axios interceptor)
  → /admin/* protected routes
  → logout → discard token; security event logged server-side
```

On 401, Axios interceptor redirects to login. JWT lifetime ~8 hours; no refresh in v1.

### 5.3 Quiz management

```
Dashboard / Quizzes
  → Create quiz (Draft)
  → Edit sections, questions, options, media, branding, QuizConfig
  → Validate → Ready
  → Archive / Restore / Duplicate / Delete (blocked if InUse)
  → Preview (solo mode, Ready only; no state change)
```

### 5.4 Live hosting

```
Select Ready quiz → Create live room (quiz → InUse; room → Setup)
  → Open lobby (room code, QR, secret display link)
  → Toggle lobby open/closed
  → Monitor participants (names, emails, connection, activity — admin only)
  → Start session
  → Control: pause / resume / advance / skip / end; kick / ban
  → Section breaks and section leaderboards as server broadcasts
  → Completed → podium / final results
  → Close room (codes/tokens expire; quiz → Ready)
```

### 5.5 History and export

```
History → browse past sessions → view results
  → trigger CSV/Excel export → download
  → delete session history (individual or bulk)
```

---

## 6. Participant Client Flows

Join flow is ≤ 3 screens before gameplay (NFR-040):

```
Screen 1: Enter room code (or QR auto-fill via /join/:roomCode)
    │
    ▼
Screen 2: Enter display name + email
    │
    ▼
Screen 3: Lobby (waiting for admin to start)
    │
    ▼
Gameplay: /join/:roomCode/play
  (question + answer selection + explicit submit;
   buzzer on buzzer question types;
   live leaderboard always visible after each question;
   final rank and score at session end)
```

### 6.1 Join and reconnection

- Successful join stores participant session token for REST and WebSocket.
- Same email in room restores participant (score + streak) and issues a new token.
- Duplicate name (new email) rejected; banned email rejected; Closed room rejected.
- WebSocket disconnect → auto-reconnect with exponential backoff → server RESYNC restores UI (room state, question + remaining timer, own score/streak/rank, leaderboard, whether already answered).

### 6.2 Gameplay interactions

- Answer selection may be optimistic in local UI before submit; score/rank only from server.
- Submit and buzz are acknowledged over WebSocket; duplicates ignored / rejected per server rules.
- Kick shows removal message and disconnects; rejoin without ban preserves progress.

### 6.3 Visibility

| Data | Self | Others | Display |
|------|------|--------|---------|
| Display name | Yes | Leaderboard | Leaderboard |
| Email | Yes | No | No |
| Score / rank | Yes | Leaderboard | Leaderboard |
| Own answers | Yes | No | No |

---

## 7. Presentation Screen Flows

```
Admin copies share link → open /display/:secretToken
  → validate secretToken maps to active room
  → WebSocket connect with secretToken (read-only)
  → receive RESYNC + room broadcasts
```

**No login. No admin controls. No participant emails.**

### 7.1 Display modes (driven by room state)

Lobby · Question · Timer · Answer reveal · Section leaderboard · Live leaderboard · Podium

### 7.2 Layout concept

```
[Logo]   Quiz Title                    Room Code: ABC123
────────────────────────────────────────────────────────
              QUESTION / LEADERBOARD
                 (primary content)
────────────────────────────────────────────────────────
[Timer bar]                              [Participant #]
```

Shows quiz title, room code, platform logo, and per-quiz branding. Timer countdown is rendered from server `timerEndsAt` (and pause/resume freezes).

---

## 8. Cross-Client Live States

Aligned with room lifecycle (architecture §7). Clients render; they do not invent transitions.

| Room state | Admin | Participant | Presentation |
|------------|-------|-------------|--------------|
| **Setup** | Create/configure room; open lobby | — | — |
| **Lobby** (Open/Closed) | Monitor; toggle lobby; start; share links | Join (if Open) → waiting lobby | Lobby display |
| **Active** | Host controls; monitor | Question / answering / buzzing / waiting; leaderboard | Question, timer, reveal, leaderboard |
| **Paused** | Resume / end | Submissions blocked; frozen timer UI | Frozen timer / paused UI |
| **SectionBreak** | Advance section | Section leaderboard | Section leaderboard |
| **Completed** | Podium/results; close room | Final rank and score | Podium |
| **Closed** | Room ended | Cannot join | Token/code expired |

Leaderboard is broadcast to all three client types after every scored question (FR-091).

---

## 9. Shared Frontend Concerns

| Concern | Approach |
|---------|----------|
| HTTP client | Axios + JWT interceptor (admin) + error normalization |
| Validation | Zod shared across forms and API parsing |
| WebSocket | Custom hook: native WebSocket, auto-reconnect, heartbeat, room resync |
| Timer display | Countdown from server `endsAt` / `timerEndsAt`; server owns expiry |
| Responsive | Tailwind; equal priority desktop/mobile for Admin and Participant |
| i18n | Extraction pattern prepared; English-only in v1 |
| Theming | Light theme only; design tokens via Tailwind |

Error UX: toast via TanStack Query global handler; form field errors from server; inline WS action errors; module error boundaries.

---

## 10. Open Items

Visual wireframes and pixel-level design are outside the architecture document. Flows above must not add screens or capabilities beyond SYSTEM_ARCHITECTURE.md §§2, 5–9.

---

*End of Document*
