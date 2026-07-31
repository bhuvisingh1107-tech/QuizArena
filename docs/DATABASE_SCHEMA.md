# QuizArena — Database Schema

| Field | Value |
|-------|-------|
| **Document Title** | QuizArena — Database Schema |
| **Version** | 1.0 |
| **Status** | Draft for Review |
| **Date** | July 31, 2026 |
| **Prepared By** | Software Architecture Team |
| **Architecture Baseline** | [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) v1.0 |
| **Requirements Baseline** | [PROJECT_SPEC.md](./PROJECT_SPEC.md) v1.1 |

---

## Table of Contents

1. [Overview](#1-overview)
2. [Database Strategy](#2-database-strategy)
3. [Content vs Session Separation](#3-content-vs-session-separation)
4. [Entity Relationship Overview](#4-entity-relationship-overview)
5. [Identity Domain](#5-identity-domain)
6. [Content Domain](#6-content-domain)
7. [Session Runtime Domain](#7-session-runtime-domain)
8. [Media Metadata Domain](#8-media-metadata-domain)
9. [Configuration Domain](#9-configuration-domain)
10. [Uniqueness Constraints](#10-uniqueness-constraints)
11. [Delete Strategies](#11-delete-strategies)
12. [Indexing Strategy](#12-indexing-strategy)
13. [Migration Strategy](#13-migration-strategy)
14. [Open Items](#14-open-items)

---

## 1. Overview

This document elaborates the conceptual data model defined in [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) §§4 and 12. Column-level SQL types and Alembic revision files are implementation artifacts; entities, relationships, constraints, and indexing intent here must stay aligned with that architecture.

SQLAlchemy is the ORM for both environments. Alembic manages schema migrations. Engine selection is driven by `DATABASE_URL`.

---

## 2. Database Strategy

| Environment | Engine | Hosting | Purpose |
|-------------|--------|---------|---------|
| **Development** | SQLite | Local filesystem | Fast local iteration, zero infrastructure |
| **Production** | PostgreSQL | Neon | Managed, serverless-compatible PostgreSQL |
| **Test** | SQLite (in-memory) | CI runner | Isolated test execution |

---

## 3. Content vs Session Separation

Quiz templates (reusable content) are decoupled from session instances (runtime data):

```
Quiz Template (durable content)          Session Instance (runtime snapshot)
─────────────────────────────           ─────────────────────────────────
Quiz                                    Live Room
  └── Section                             └── Session Participant
        └── Question                            └── Session Response
              └── Answer Option                         └── Score Record
```

When a live room is created from a quiz, the backend creates an immutable **session snapshot** of the quiz structure. Changes to the quiz template after room creation do not affect an active or completed session (NFR-072).

Snapshot mapping (architecture §8.4):

```
Quiz          → LiveRoom (quizSnapshot)
Section       → SessionSection
Question      → SessionQuestion
AnswerOption  → SessionOption
QuizConfig    → RoomConfig
```

Snapshot preserves question order, options, correct answers, point values, and quiz configuration at room creation. Session snapshots store media **file reference IDs**, not copies of files.

---

## 4. Entity Relationship Overview

```
Admin
  └── creates/manages → Quiz
                          ├── 1:1 QuizConfig
                          ├── 1:N Section → 1:N Question → 1:N AnswerOption
                          │                      └── N:1 MediaFile (optional)
                          ├── 1:N MediaFile (branding)
                          └── 1:N LiveRoom
                                        ├── 1:1 RoomConfig
                                        ├── 1:N Participant → 1:N Response
                                        └── 1:N SessionQuestion → 1:N SessionOption

SecurityLog (standalone audit trail)
```

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

---

## 5. Identity Domain

### 5.1 Admin

Single administrator account for v1 (seeded via CLI / deploy).

| Conceptual field | Notes (from architecture) |
|------------------|---------------------------|
| Identifier | JWT `sub` |
| Username | Seeded via `ADMIN_USERNAME` |
| Password hash | bcrypt or argon2; never plaintext |
| Role | `admin` only in v1 |

### 5.2 SecurityLog

Standalone audit trail for authentication security events.

| Event types persisted | Source |
|-----------------------|--------|
| Login success | Auth flow |
| Logout | Auth flow |
| Failed authentication | Auth flow / monitoring |

Passwords, JWT tokens, and participant emails must not appear in error logs (architecture §13.5). Security event logging is separate from application error logs.

---

## 6. Content Domain

### 6.1 Quiz

Durable quiz template. Lifecycle states (architecture §8.1):

`Draft` → `Ready` → `InUse` | `Archived` | `Deleted`  
`Archived` → `Ready` (restore)  
`InUse` → `Ready` when room closes

| Conceptual concern | Notes |
|--------------------|-------|
| Title | Required for Ready validation |
| Status | Draft / Ready / InUse / Archived / Deleted |
| Branding | Optional quiz logo via MediaFile |
| InUse lock | Set on room creation; restored to Ready on room Closed |
| Soft delete | Deleted state; hard delete option; blocked when InUse |

### 6.2 Section

Ordered sections within a quiz. Ready validation requires at least one section, each with at least one question. Total questions across the quiz ≤ 100.

### 6.3 Question

Ordered questions within a section.

| Conceptual concern | Notes |
|--------------------|-------|
| Prompt content | Text, image, and/or audio as required by type |
| Question types | Include image, audio, and buzzer types (per client/scoring architecture) |
| Base point value | ≥ 1 |
| Options | 2–6 AnswerOption rows; ≥ 1 correct |
| Media reference | Optional FK to MediaFile |
| Order | Within section |

### 6.4 AnswerOption

| Conceptual concern | Notes |
|--------------------|-------|
| Option content | Text (and related display data as implemented) |
| Correct flag | At least one correct option per question |
| Order | Within question |

### 6.5 QuizConfig

1:1 with Quiz. Holds scoring and behavior settings used by ScoringService / Timer Service (time bonus, streak bonus, auto-advance, timers — as defined in SRS Section 12 and quiz configuration).

---

## 7. Session Runtime Domain

### 7.1 LiveRoom

Runtime session instance created from a Ready quiz.

| Conceptual field / concern | Notes |
|----------------------------|-------|
| Room state | Setup, Lobby, Active, Paused, SectionBreak, Completed, Closed |
| Lobby sub-state | LobbyOpen / LobbyClosed (while in Lobby) |
| roomCode | 6-character alphanumeric; unique while active; expired on Closed |
| secretToken | High-entropy display access token; unique while active |
| Quiz reference + snapshot | Immutable session copy of content/config |
| QR / share link material | Derived from roomCode and secretToken |

**Persistence vs memory:** Durable session records live in PostgreSQL. An in-memory room runtime context holds hot-path state (current question, timer, buzzer lock, live leaderboard, connected clients). State transitions write through to the database immediately. Participant responses and scores persist on each scored question. Full session snapshot is persisted before Completed.

### 7.2 RoomConfig

1:1 with LiveRoom. Immutable snapshot of QuizConfig at room creation.

### 7.3 SessionQuestion / SessionOption

Immutable copies of questions and options for the session (including order, correct answers, point values). May be organized under session sections consistent with the template snapshot.

### 7.4 Participant

| Conceptual field / concern | Notes |
|----------------------------|-------|
| displayName | Unique per room |
| email | Unique per room; used for reconnection and ban list |
| Session token | Cryptographically random; room-scoped lifetime |
| State | Joining, InLobby, Active, Answering, Buzzing, Answered, Waiting, BuzzUnlocked, Disconnected, Reconnecting, Kicked, Banned, SessionEnded |
| Score / streak / rank | Updated by ScoringService / LeaderboardService |
| Connection status | Visible to admin only |

### 7.5 Response

One response per question per participant. Persists answer selection/submission and awarded points. Duplicate submit for the same question is ignored (idempotent).

### 7.6 Room ban list

Per-room ban of participant emails (kick + ban). Join rejects banned emails for that room.

### 7.7 Session history

Completed session records browsable by admin; hard-deletable individually or in bulk. Participant data hard-deletes cascade with session deletion.

---

## 8. Media Metadata Domain

### 8.1 MediaFile

Database stores file **metadata**; bytes live on the storage backend (`storage/images`, `storage/audio`, `storage/branding/...`).

| Conceptual field | Notes |
|------------------|-------|
| storageKey | UUID-based path; unique |
| Category | Question image, question audio, quiz branding, platform branding |
| MIME type | Validated via magic bytes on upload |
| File size | Enforced per category limits |
| Public URL / reference ID | Returned to clients; questions/quizzes store reference IDs |

| Category | Formats | Max size |
|----------|---------|----------|
| Question image | JPEG, PNG, WebP | 5 MB |
| Question audio | MP3, WAV | 15 MB |
| Quiz branding | JPEG, PNG, WebP | 2 MB |
| Platform branding | JPEG, PNG, WebP | 2 MB |

---

## 9. Configuration Domain

Platform settings and branding defaults (architecture §4.2), including platform logo MediaFile references managed via the Settings resource group.

---

## 10. Uniqueness Constraints

| Scope | Fields | Purpose |
|-------|--------|---------|
| LiveRoom | roomCode (while active) | Join lookup |
| LiveRoom | secretToken (while active) | Display access |
| Participant (per room) | displayName | SRS FR-064 |
| Participant (per room) | email | SRS FR-063 |
| MediaFile | storageKey | Filesystem path uniqueness |

---

## 11. Delete Strategies

| Entity | Delete strategy |
|--------|-----------------|
| **Quiz** | Soft delete (Deleted state) with hard delete option; blocked when InUse |
| **Session history** | Hard delete (admin-initiated, individual or bulk) |
| **Media files** | Hard delete from storage + database (orphan check on question delete; all quiz media on quiz delete) |
| **Participant data** | Hard delete cascades with session deletion |

---

## 12. Indexing Strategy

Indexes planned around these query patterns (architecture §4.5):

- Quiz library listing and search by title/status
- Live room lookup by room code (join flow hot path)
- Session history listing by date
- Participant lookup by room + email (uniqueness check, reconnection)
- Session responses by room + participant (export generation)

---

## 13. Migration Strategy

| Aspect | Approach |
|--------|----------|
| **Tool** | Alembic with autogenerate review workflow |
| **Naming** | Timestamp-prefixed revision files |
| **Development** | Migrations applied on startup or via CLI |
| **Production** | Migrations run in Render deploy pipeline before app start |
| **Rollback** | Downgrade scripts maintained for each revision |
| **Seeding** | Admin account seeded via CLI (`scripts/seed_admin.py`) or startup script |

---

## 14. Open Items

Per architecture §12, detailed physical column types, precise FK cascade rules, and Alembic revision contents remain implementation decisions. They must not introduce entities or relationships beyond those listed here and in SYSTEM_ARCHITECTURE.md.

---

*End of Document*
