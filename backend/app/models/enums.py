"""Domain enumerations persisted as portable string values."""

from enum import StrEnum


class AdminRole(StrEnum):
    ADMIN = "admin"


class QuizStatus(StrEnum):
    DRAFT = "Draft"
    READY = "Ready"
    IN_USE = "InUse"
    ARCHIVED = "Archived"
    DELETED = "Deleted"


class QuestionType(StrEnum):
    TEXT = "Text"
    IMAGE = "Image"
    AUDIO = "Audio"
    BUZZER = "Buzzer"


class QuestionAdvanceMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class AnswerRevealBehavior(StrEnum):
    AFTER_EACH = "after_each"
    SESSION_END = "session_end"


class RoomState(StrEnum):
    SETUP = "Setup"
    LOBBY = "Lobby"
    ACTIVE = "Active"
    PAUSED = "Paused"
    SECTION_BREAK = "SectionBreak"
    COMPLETED = "Completed"
    CLOSED = "Closed"


class LobbySubState(StrEnum):
    OPEN = "LobbyOpen"
    CLOSED = "LobbyClosed"


class SessionQuestionState(StrEnum):
    PENDING = "Pending"
    OPEN = "Open"
    BUZZER_OPEN = "BuzzerOpen"
    BUZZER_LOCKED = "BuzzerLocked"
    CLOSED = "Closed"
    REVEALED = "Revealed"
    SCORED = "Scored"


class ParticipantState(StrEnum):
    JOINING = "Joining"
    IN_LOBBY = "InLobby"
    ACTIVE = "Active"
    ANSWERING = "Answering"
    BUZZING = "Buzzing"
    BUZZ_UNLOCKED = "BuzzUnlocked"
    ANSWERED = "Answered"
    WAITING = "Waiting"
    DISCONNECTED = "Disconnected"
    RECONNECTING = "Reconnecting"
    KICKED = "Kicked"
    BANNED = "Banned"
    SESSION_ENDED = "SessionEnded"


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class MediaCategory(StrEnum):
    QUESTION_IMAGE = "question_image"
    QUESTION_AUDIO = "question_audio"
    QUIZ_BRANDING = "quiz_branding"
    PLATFORM_BRANDING = "platform_branding"


class SecurityEventType(StrEnum):
    LOGIN_SUCCESS = "login_success"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
