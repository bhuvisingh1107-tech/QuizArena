"""Question timer helpers.

Authoritative open timestamps live on ``SessionQuestion.opened_at``.
WebSocket payloads expose ``timerEndsAt`` = opened_at + time_limit_seconds.
"""
