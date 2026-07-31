"""FastAPI dependency injection (auth, db session)."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.models.admin import Admin
from app.models.participant import Participant
from app.services.auth_service import AuthService, RequestContext
from app.services.participant_service import ParticipantService

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

bearer_scheme = HTTPBearer(auto_error=False)


def get_engine(settings: Settings | None = None) -> Engine:
    """Return the SQLAlchemy engine, creating it on first use."""
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
        _engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return the session factory bound to the engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(settings),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed after use."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection(session: Session) -> bool:
    """Verify database connectivity for health checks."""
    session.execute(text("SELECT 1"))
    return True


def get_request_id(request: Request) -> str:
    """Extract the correlation ID attached by RequestIdMiddleware."""
    return getattr(request.state, "request_id", "")


def get_request_context(request: Request) -> RequestContext:
    """Build security-log context from the HTTP request (no secrets)."""
    forwarded = request.headers.get("X-Forwarded-For")
    ip_address = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    user_agent = request.headers.get("User-Agent")
    return RequestContext(ip_address=ip_address, user_agent=user_agent)


def get_auth_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(db, settings)


def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Admin:
    """Require a valid admin JWT Bearer token (FR-002)."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationError("AUTH_ERROR", "Missing authentication token")
    return auth_service.get_admin_from_token(credentials.credentials)


def get_current_participant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Participant:
    """Require a valid participant session token (architecture §5.2)."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationError("INVALID_PARTICIPANT_TOKEN", "Missing participant session token")
    return ParticipantService(db).get_by_token(credentials.credentials)


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
RequestId = Annotated[str, Depends(get_request_id)]
CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
CurrentParticipant = Annotated[Participant, Depends(get_current_participant)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
