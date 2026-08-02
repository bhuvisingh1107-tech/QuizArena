"""Administrator / host account model (DATABASE_SCHEMA.md §5.1).

Table name remains ``admins`` for API compatibility; the product UI calls these hosts.
"""

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import AdminRole


class Admin(Base, TimestampMixin):
    """Host account that owns quizzes and can run live rooms."""

    __tablename__ = "admins"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        str_enum(AdminRole, length=16),
        nullable=False,
        default=AdminRole.ADMIN,
        server_default=AdminRole.ADMIN.value,
    )
