"""Seed the administrator account.

Usage:
    python -m scripts.seed_admin
    # or: python scripts/seed_admin.py

Environment (SYSTEM_ARCHITECTURE.md §18.3):
    ADMIN_USERNAME       — admin username (default: admin)
    ADMIN_PASSWORD       — plaintext password (hashed before storage; preferred for local seed)
    ADMIN_PASSWORD_HASH  — pre-computed bcrypt hash (used when ADMIN_PASSWORD is unset)

Password must satisfy FR-005 when providing ADMIN_PASSWORD.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running as ``python scripts/seed_admin.py`` from backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.config import get_settings  # noqa: E402
from app.core.password_policy import validate_password_policy  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.api.deps import get_engine, get_session_factory  # noqa: E402
from app.repositories.admin_repository import AdminRepository  # noqa: E402


def main() -> None:
    settings = get_settings()
    username = os.getenv("ADMIN_USERNAME", settings.admin_username) or "admin"
    plaintext = os.getenv("ADMIN_PASSWORD", "").strip()
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", settings.admin_password_hash).strip()

    if plaintext:
        validate_password_policy(plaintext)
        password_hash = hash_password(plaintext)
    elif not password_hash:
        print(
            "ERROR: Set ADMIN_PASSWORD (plaintext, will be hashed) "
            "or ADMIN_PASSWORD_HASH (bcrypt hash).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Ensure engine/session bind to current settings
    get_engine(settings)
    session = get_session_factory(settings)()
    try:
        repo = AdminRepository(session)
        existing = repo.get_by_username(username)
        if existing is not None:
            print(f"Admin '{username}' already exists (id={existing.id}). Skipping.")
            return

        admin = repo.create(username=username, password_hash=password_hash)
        session.commit()
        print(f"Seeded admin '{admin.username}' (id={admin.id}).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
