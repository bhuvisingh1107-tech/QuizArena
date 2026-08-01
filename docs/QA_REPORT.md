# QuizArena QA Report

**Date:** 2026-07-31  
**Scope:** Production-release QA (functional, edge, responsive, a11y, performance, security)  
**Constraint:** No new features — stabilize, optimize, polish only  
**Production readiness score:** **8.2 / 10**

## Verdict

QuizArena is ready for a **controlled production launch** after this stabilization pass. All discovered P0/P1 defects were fixed. Automated suites are green (**167** backend + **44** frontend). Defer hard multi-instance scale-out until sticky sessions and 100-client load tests are complete.

---

## Bugs found

| Sev | ID | Area | Issue |
|-----|-----|------|--------|
| P0 | QA-01 | Scoring | Time bonus configured but never awarded (`response_time_ms` always null) |
| P0 | QA-02 | Live session | Pause did not freeze question timers (server or clients) |
| P0 | QA-03 | Answers | Submit crashed on naive vs aware datetime (`opened_at`); WS hung waiting for accept |
| P1 | QA-04 | Auth | Expired admin JWT cleared on REST but WS still accepted control events |
| P1 | QA-05 | Join | Concurrent duplicate names → 500; names were case-sensitive |
| P1 | QA-06 | Answers | Concurrent double-submit → uncaught IntegrityError |
| P1 | QA-07 | Display | Podium ties collapsed top-3 slots via rank map |
| P1 | QA-08 | Pause | REST pause/resume did not broadcast to participants/display |
| P2 | QA-09 | Export | CSV export JSON errors returned as opaque Blob |
| P2 | QA-10 | Quizzes | Hard-delete quiz with room history → 500 (FK RESTRICT) |
| P2 | QA-11 | Join UX | Join navigated to `/lobby` before refresh settled |
| P2 | QA-12 | Media | `Content-Disposition` used unsanitized filename |
| P2 | QA-13 | Reconnect | Handshake overwrote pause-aware `timerEndsAt` |

---

## Bugs fixed

All **13 / 13** findings above were fixed. Highlights:

- Pause tracking (`paused_at`, `pause_accumulated_ms`) with pause-aware `timerEndsAt` / `response_time_ms` / time bonus
- Client timers freeze while `Paused`; resume updates deadline from server
- REST + WS pause/resume broadcast lifecycle events with timer fields
- Admin JWT re-validated on WS control events; client clears auth at `expiresAt`
- Join conflict handling, case-insensitive names, abandoned-name reclaim
- Double-submit → `ALREADY_SUBMITTED`
- Podium uses ordered top-3 slice (ties fill slots)
- Hard-delete blocked with `QUIZ_HAS_ROOMS`
- CSV export parses JSON error blobs
- Media filename sanitized for `Content-Disposition`
- SQLite-safe UTC normalization for datetime arithmetic

---

## Remaining known limitations

| Area | Limitation |
|------|------------|
| Load | 100 concurrent participants not load-tested in this pass (soft cap = 100) |
| Load | 100+ question quizzes not soak-tested under projector + many clients |
| Network | True offline / flaky-network chaos limited to reconnect unit paths |
| PDF | “Export PDF” is browser `print`, not a server-generated PDF binary |
| A11y | Partial automated coverage; full screen-reader device lab not completed |
| Scale | Single-node WebSocket fan-out; HA needs sticky sessions / shared pub-sub |

---

## Verification

```text
Backend:  PYTHONPATH=. pytest -q   → 167 passed
Frontend: npm test -- --run        → 44 passed
Frontend: npm run build            → OK (route-split chunks)
```

Bundle (approx gzip): admin routes ~51 kB, participant ~14 kB, display ~12 kB, vendor-react ~79 kB.

---

## Score rationale (8.2 / 10)

Points awarded for closed P0/P1s, green automation, and stabilized live flows (pause, scoring, join, JWT). Points withheld for unverified 100-client load, print-based PDF, and incomplete manual a11y/responsive device lab.
