# QuizArena — Socket Events

| Field | Value |
|-------|-------|
| **Document Title** | QuizArena — Socket Events |
| **Version** | 1.0 |
| **Status** | Draft for Review |
| **Date** | July 31, 2026 |
| **Prepared By** | Software Architecture Team |
| **Architecture Baseline** | [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) v1.0 |
| **Requirements Baseline** | [PROJECT_SPEC.md](./PROJECT_SPEC.md) v1.1 |
| **Related** | [API_SPEC.md](./API_SPEC.md), [UI_FLOW.md](./UI_FLOW.md) |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Connection Model](#2-connection-model)
3. [Connection Lifecycle](#3-connection-lifecycle)
4. [Message Format](#4-message-format)
5. [Broadcast Rules](#5-broadcast-rules)
6. [Named Server Events](#6-named-server-events)
7. [Event Categories](#7-event-categories)
8. [Client → Server Actions](#8-client--server-actions)
9. [Timer Synchronization](#9-timer-synchronization)
10. [Reconnection and Resync](#10-reconnection-and-resync)
11. [Errors](#11-errors)
12. [Open Items](#12-open-items)

---

## 1. Overview

Real-time synchronization uses **native WebSockets** via FastAPI (architecture decision: not Socket.IO). All live session events flow through a **room-scoped** pub/sub channel managed by the WebSocket Manager.

REST handles CRUD, auth, uploads, exports, and join token issuance. WebSockets handle live state, questions, timers, scoring, leaderboard, presence, and host controls.

| Item | Value |
|------|-------|
| Transport | Native WebSocket (WSS in production) |
| Frontend base | `VITE_WS_BASE_URL` |
| Backend | Co-located with REST on the same FastAPI process |
| Auth on connect | Token as query parameter |
| Protocol version | Included in connect handshake (for future compatibility) |

---

## 2. Connection Model

```
WebSocket Manager
  rooms: Map<roomId, Set>
    ├── admin: WSConnection          (1 per room)
    ├── display: WSConnection        (1 per room)
    └── participants: Map<id, WS>    (up to 100)
```

| Role | Authenticate with | Channel behavior |
|------|-------------------|------------------|
| **Admin** | JWT | Bidirectional |
| **Participant** | Participant session token | Bidirectional |
| **Display** | secretToken | Receive-only (no control events) |

Architecture allows one unified WebSocket endpoint with role identified on connect, or separate endpoints per client type.

---

## 3. Connection Lifecycle

```
CONNECT
  ├── Admin: JWT → join room admin channel
  ├── Participant: session token → join room participant channel
  └── Display: secretToken → join room display channel
        │
        ▼
SERVER sends RESYNC snapshot (full room state for client type)
        │
        ▼
ACTIVE
  ├── Heartbeat ping/pong every 30s
  ├── Client events → backend validates → state change → broadcast
  └── Server events → broadcast per broadcast rules
        │
        ▼
DISCONNECT
  ├── Admin: log disconnect; room continues (admin may reconnect)
  ├── Participant: mark Disconnected; allow auto-reconnect with resync
  └── Display: remove from channel; may reconnect freely
```

---

## 4. Message Format

| Principle | Standard |
|-----------|----------|
| Format | JSON |
| Fields | `type`, `payload`, `timestamp` |
| Acknowledgment | Critical client actions (submit answer, buzz) receive ack messages |
| Ordering | Events for a single room emitted in causal order; clients apply sequentially |
| Isolation | Never broadcast across room boundaries |

---

## 5. Broadcast Rules

| Rule | Description |
|------|-------------|
| **Room-scoped isolation** | Events never cross room boundaries |
| **Leaderboard mandatory** | Every `question:scored` is followed by `leaderboard:updated` to all three client types |
| **Display is read-only** | Display receives broadcasts; sends no control events |
| **Admin-only events** | Participant emails and kick/ban confirmations → admin channel only |
| **Participant-specific** | Buzz accept/reject → target participant (+ admin monitoring) |
| **Ordering guarantee** | Causal order within a room |

---

## 6. Named Server Events

The following event type names appear explicitly in SYSTEM_ARCHITECTURE.md. Implementations should use these names (or document a deliberate rename in this file).

| Event `type` | When | Recipients |
|--------------|------|------------|
| `room:lobbyOpened` | Setup → Lobby; lobby open | Room clients |
| `room:sessionStarted` | Lobby → Active | Room clients |
| `room:paused` | Active → Paused (frozen state) | Room clients |
| `room:resumed` | Paused → Active | Room clients |
| `room:completed` | Session ends; includes podium data | Room clients |
| `section:break` | Last question in section scored; section leaderboard | Room clients |
| `section:continued` | Admin advances from SectionBreak | Room clients |
| `question:scored` | Scoring pipeline complete for a question | All room clients |
| `leaderboard:updated` | Immediately after every `question:scored` | Admin, all participants, display |
| `participant:joined` | New or restored participant accepted | Admin (presence) |

**RESYNC** (on connect/reconnect): full state snapshot for the client type—not necessarily a single named `type` string in architecture, but a mandatory server→client sync message category.

Additional room/question events (lobby closed, question presented, timer started/expired, answer revealed, etc.) are required by architecture categories (§6.3) even where a final `type` string is not listed; see §7.

---

## 7. Event Categories

Architecture groups events as follows. Payload schemas are implementation detail; behavior must match these categories.

| Category | Direction | Examples from architecture |
|----------|-----------|----------------------------|
| **Room state** | Server → All | Room state changed; lobby opened/closed; session started/paused/ended |
| **Question** | Server → All | Question presented; timer started/tick/expired; answer revealed |
| **Participant action** | Client → Server | Join (WS path if used); submit answer; buzz |
| **Participant feedback** | Server → Client | Buzz accepted/rejected; answer recorded |
| **Scoring** | Server → All | Question scored; streak updated |
| **Leaderboard** | Server → All | Leaderboard updated (after every question, mandatory) |
| **Participant presence** | Server → Admin | Joined, disconnected, reconnected, kicked |
| **Admin control** | Client → Server | Start, pause, resume, skip, advance, end, kick, ban |
| **Section** | Server → All | Section break started; section leaderboard displayed |
| **Sync** | Server → Client | Full state resync on connect/reconnect |

---

## 8. Client → Server Actions

### 8.1 Admin control

Validated by Room Service / state machines. Invalid transitions rejected without side effect.

| Action | Effect (architecture) |
|--------|------------------------|
| Open lobby | Setup → Lobby; codes/links; `room:lobbyOpened` |
| Start session | Lobby → Active; `room:sessionStarted` |
| Pause | Active → Paused; `room:paused` |
| Resume | Paused → Active; `room:resumed` |
| Skip / advance | Question / section progression |
| End session | → Completed; `room:completed` + podium |
| Close room | → Closed; expire tokens |
| Kick / ban | Remove from channel; optional ban list |

### 8.2 Participant actions

| Action | Notes |
|--------|-------|
| Submit answer | Only when question Open (or eligible under BuzzerLocked); idempotent |
| Buzz | First buzz wins lock; subsequent rejected; ack/reject to actor + admin |

Display sends **no** control events.

---

## 9. Timer Synchronization

Timers are server-authoritative (ASM-007):

- On question open: server sets `timerEndsAt` (absolute UTC) and broadcasts it
- Clients compute countdown locally from `timerEndsAt`
- Server timer task fires at expiry regardless of clients
- Pause: broadcast `timerPausedAt` with remaining milliseconds; clients freeze
- Resume: broadcast new `timerEndsAt`; clients resume

Timer expiry closes the question and triggers the scoring pipeline (and auto-advance when configured).

---

## 10. Reconnection and Resync

```
Disconnect detected
  → auto-reconnect with exponential backoff (1s, 2s, 4s, max 10s)
  → reconnect with session token (participant) / JWT (admin) / secretToken (display)
  → server validates → RESYNC payload:
        - Current room state
        - Current question state + remaining timer
        - Participant's own score, streak, rank (participant)
        - Current leaderboard
        - Whether participant already answered current question
  → client restores UI to match server
```

---

## 11. Errors

WebSocket errors use structured codes aligned with architecture §13.1:

| Code | Meaning |
|------|---------|
| `VALIDATION_ERROR` | Invalid payload |
| `AUTH_ERROR` | Expired/invalid token |
| `FORBIDDEN` | Role cannot perform action |
| `NOT_FOUND` | Unknown room/resource |
| `CONFLICT` | Duplicate / conflicting state |
| `BUSINESS_RULE` | Invalid transition, buzz after lock, etc. |
| `INTERNAL_ERROR` | Unexpected failure |

Error events go to the **initiating client only** (not broadcast). Rate limiting applies to REST login/join; architecture does not define a WS rate-limit code.

---

## 12. Open Items

Architecture §6.3 states that complete event names and payloads are refined in the API/socket specification phase. This document freezes names that already appear in SYSTEM_ARCHITECTURE.md and the category/behavior contract. Implementations must not add features outside those categories (e.g. cross-room chat, multi-display control).

---

*End of Document*
