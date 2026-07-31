"""Pydantic request/response schemas."""

from app.schemas.answer_option import (
    AnswerOptionCreateRequest,
    AnswerOptionDeleteData,
    AnswerOptionListData,
    AnswerOptionResponseData,
    AnswerOptionUpdateRequest,
)
from app.schemas.auth import (
    AdminResponseData,
    LoginRequest,
    LoginResponseData,
    LogoutResponseData,
)
from app.schemas.common import DataResponse, ErrorResponse, HealthData, Meta
from app.schemas.live_room import (
    LiveRoomCreateRequest,
    LiveRoomDeleteData,
    LiveRoomListData,
    LiveRoomResponseData,
    RoomConfigData,
    RoomConfigResponseData,
)
from app.schemas.media import (
    MediaAttachData,
    MediaAttachRequest,
    MediaDeleteData,
    MediaResponseData,
)
from app.schemas.participant import (
    JoinRequest,
    JoinResponseData,
    JoinRoomMetaData,
    LeaveResponseData,
    ParticipantResponseData,
)
from app.schemas.question import (
    QuestionCreateRequest,
    QuestionDeleteData,
    QuestionListData,
    QuestionResponseData,
    QuestionUpdateRequest,
)
from app.schemas.quiz import (
    QuizConfigData,
    QuizCreateRequest,
    QuizDeleteData,
    QuizListData,
    QuizResponseData,
    QuizUpdateRequest,
)
from app.schemas.section import (
    SectionCreateRequest,
    SectionDeleteData,
    SectionListData,
    SectionResponseData,
    SectionUpdateRequest,
)

__all__ = [
    "AdminResponseData",
    "AnswerOptionCreateRequest",
    "AnswerOptionDeleteData",
    "AnswerOptionListData",
    "AnswerOptionResponseData",
    "AnswerOptionUpdateRequest",
    "DataResponse",
    "ErrorResponse",
    "HealthData",
    "JoinRequest",
    "JoinResponseData",
    "JoinRoomMetaData",
    "LeaveResponseData",
    "LiveRoomCreateRequest",
    "LiveRoomDeleteData",
    "LiveRoomListData",
    "LiveRoomResponseData",
    "LoginRequest",
    "LoginResponseData",
    "LogoutResponseData",
    "MediaAttachData",
    "MediaAttachRequest",
    "MediaDeleteData",
    "MediaResponseData",
    "Meta",
    "ParticipantResponseData",
    "QuestionCreateRequest",
    "QuestionDeleteData",
    "QuestionListData",
    "QuestionResponseData",
    "QuestionUpdateRequest",
    "QuizConfigData",
    "QuizCreateRequest",
    "QuizDeleteData",
    "QuizListData",
    "QuizResponseData",
    "QuizUpdateRequest",
    "RoomConfigData",
    "RoomConfigResponseData",
    "SectionCreateRequest",
    "SectionDeleteData",
    "SectionListData",
    "SectionResponseData",
    "SectionUpdateRequest",
]
