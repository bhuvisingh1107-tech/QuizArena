"""WebSocket event type constants (SOCKET_EVENTS.md)."""

from enum import StrEnum


class ClientRole(StrEnum):
    ADMIN = "admin"
    PARTICIPANT = "participant"
    DISPLAY = "display"


class ServerEventType(StrEnum):
    """Server → client event types."""

    CONNECTION_ACK = "connection:ack"
    RESYNC = "resync"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"

    # Presence (admin channel)
    PARTICIPANT_JOINED = "participant:joined"
    PARTICIPANT_LEFT = "participant:left"
    PARTICIPANT_RECONNECTED = "participant:reconnected"
    PARTICIPANT_DISCONNECTED = "participant:disconnected"

    # Room state (documented names)
    ROOM_STATE_CHANGED = "room:state_changed"
    ROOM_LOBBY_OPENED = "room:lobbyOpened"
    ROOM_LOBBY_CLOSED = "room:lobbyClosed"
    ROOM_SESSION_STARTED = "room:sessionStarted"
    ROOM_PAUSED = "room:paused"
    ROOM_RESUMED = "room:resumed"
    ROOM_COMPLETED = "room:completed"
    ROOM_CLOSED = "room:closed"

    # Section / quiz execution
    SECTION_STARTED = "section:started"
    SECTION_BREAK = "section:break"
    SECTION_CONTINUED = "section:continued"
    QUESTION_STARTED = "question:started"
    QUESTION_CLOSED = "question:closed"
    QUESTION_REVEAL = "question:reveal"
    QUIZ_COMPLETED = "quiz:completed"

    # Answer submission
    ANSWER_ACCEPTED = "answer:accepted"
    ANSWER_UPDATED = "answer:updated"
    ANSWER_REJECTED = "answer:rejected"
    ANSWER_RECEIVED = "answer:received"
    ANSWER_SUBMISSION_COUNT = "answer:submission_count"

    # Explicitly deferred (scoring / leaderboard modules)
    QUESTION_SCORED = "question:scored"
    LEADERBOARD_UPDATED = "leaderboard:updated"


class ClientEventType(StrEnum):
    """Client → server event types handled by the dispatcher."""

    PING = "ping"
    PONG = "pong"

    # Admin control → routed to LiveRoomService
    ADMIN_OPEN_LOBBY = "admin:open_lobby"
    ADMIN_TOGGLE_LOBBY = "admin:toggle_lobby"
    ADMIN_START = "admin:start_session"
    ADMIN_PAUSE = "admin:pause"
    ADMIN_RESUME = "admin:resume"
    ADMIN_END = "admin:end_session"
    ADMIN_CLOSE = "admin:close_room"

    # Admin quiz execution → QuizExecutionService
    ADMIN_START_QUESTION = "admin:start_question"
    ADMIN_CLOSE_QUESTION = "admin:close_question"
    ADMIN_REVEAL_ANSWER = "admin:reveal_answer"
    ADMIN_NEXT_QUESTION = "admin:next_question"
    ADMIN_NEXT_SECTION = "admin:next_section"
    ADMIN_END_QUIZ = "admin:end_quiz"
    ADMIN_ADVANCE = "admin:advance"

    # Participant answer submission
    PARTICIPANT_SUBMIT = "answer:submit"

    # Deferred (moderation / buzzer)
    ADMIN_SKIP = "admin:skip"
    ADMIN_KICK = "admin:kick"
    ADMIN_BAN = "admin:ban"
    PARTICIPANT_BUZZ = "buzz"


DISPLAY_FORBIDDEN_EVENTS = frozenset(ClientEventType)

DEFERRED_CLIENT_EVENTS = frozenset(
    {
        ClientEventType.ADMIN_SKIP,
        ClientEventType.ADMIN_KICK,
        ClientEventType.ADMIN_BAN,
        ClientEventType.PARTICIPANT_BUZZ,
    }
)

EXECUTION_CLIENT_EVENTS = frozenset(
    {
        ClientEventType.ADMIN_START_QUESTION,
        ClientEventType.ADMIN_CLOSE_QUESTION,
        ClientEventType.ADMIN_REVEAL_ANSWER,
        ClientEventType.ADMIN_NEXT_QUESTION,
        ClientEventType.ADMIN_NEXT_SECTION,
        ClientEventType.ADMIN_END_QUIZ,
        ClientEventType.ADMIN_ADVANCE,
    }
)
