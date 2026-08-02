"""Admin / host data access."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.admin import Admin


class AdminRepository:
    """Repository for host (admin) account records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> Admin | None:
        stmt = select(Admin).where(func.lower(Admin.username) == username.strip().lower())
        return self._session.scalar(stmt)

    def get_by_email(self, email: str) -> Admin | None:
        stmt = select(Admin).where(func.lower(Admin.email) == email.strip().lower())
        return self._session.scalar(stmt)

    def get_by_username_or_email(self, identifier: str) -> Admin | None:
        value = identifier.strip().lower()
        stmt = select(Admin).where(
            or_(
                func.lower(Admin.username) == value,
                func.lower(Admin.email) == value,
            ),
        )
        return self._session.scalar(stmt)

    def get_by_id(self, admin_id: UUID) -> Admin | None:
        return self._session.get(Admin, admin_id)

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        name: str = "",
        email: str | None = None,
    ) -> Admin:
        admin = Admin(
            username=username.strip(),
            password_hash=password_hash,
            name=name.strip(),
            email=email.strip().lower() if email else None,
        )
        self._session.add(admin)
        self._session.flush()
        return admin

    def update_password_hash(self, admin: Admin, password_hash: str) -> Admin:
        admin.password_hash = password_hash
        self._session.flush()
        return admin

    def exists_any(self) -> bool:
        return self._session.scalar(select(Admin.id).limit(1)) is not None
