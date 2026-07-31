"""Administrator account model (DATABASE_SCHEMA.md §5.1)."""

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import AdminRole


class Admin(Base, TimestampMixin):
    """Single platform administrator (seeded at deploy)."""

    __tablename__ = "admins"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        str_enum(AdminRole, length=16),
        nullable=False,
        default=AdminRole.ADMIN,
        server_default=AdminRole.ADMIN.value,
    )
