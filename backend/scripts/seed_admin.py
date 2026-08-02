"""Seed the administrator account.

Usage:
    python -m scripts.seed_admin
    # or: python scripts/seed_admin.py

Prefer relying on application startup bootstrap (AuthService.ensure_bootstrap_admin).
This CLI remains for local/manual use and reuses the same AuthService path.

Environment:
    ADMIN_USERNAME       — admin username (default: admin)
    ADMIN_PASSWORD       — plaintext password (hashed before storage; preferred)
    ADMIN_PASSWORD_HASH  — pre-computed bcrypt hash (used when ADMIN_PASSWORD is unset)

Password must satisfy FR-005 when providing ADMIN_PASSWORD.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as ``python scripts/seed_admin.py`` from backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.api.deps import get_engine, get_session_factory  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


def main() -> None:
    settings = get_settings()
    get_engine(settings)
    session = get_session_factory(settings)()
    try:
        created = AuthService(session, settings).ensure_bootstrap_admin()
        if created:
            print(f"Created initial admin '{settings.admin_username or 'admin'}'.")
        else:
            print("Admin already exists.")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
