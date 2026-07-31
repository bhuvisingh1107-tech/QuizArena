"""Admin data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import Admin


class AdminRepository:
    """Repository for Administrator account records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> Admin | None:
        stmt = select(Admin).where(Admin.username == username)
        return self._session.scalar(stmt)

    def get_by_id(self, admin_id: UUID) -> Admin | None:
        return self._session.get(Admin, admin_id)

    def create(self, *, username: str, password_hash: str) -> Admin:
        admin = Admin(username=username, password_hash=password_hash)
        self._session.add(admin)
        self._session.flush()
        return admin

    def exists_any(self) -> bool:
        return self._session.scalar(select(Admin.id).limit(1)) is not None
