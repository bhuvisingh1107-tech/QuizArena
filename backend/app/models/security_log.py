"""Security audit log model (DATABASE_SCHEMA.md §5.2)."""

from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, CreatedAtMixin, str_enum
from app.models.enums import SecurityEventType


class SecurityLog(Base, CreatedAtMixin):
    """Standalone authentication security event trail."""

    __tablename__ = "security_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[SecurityEventType] = mapped_column(
        str_enum(SecurityEventType, length=32),
        nullable=False,
        index=True,
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
