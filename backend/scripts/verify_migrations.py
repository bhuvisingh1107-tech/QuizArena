#!/usr/bin/env python3
"""Verify Alembic migrations are applied and match the repository head."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> int:
    settings = get_settings()
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        print(f"ERROR: expected a single migration head, found: {heads}", file=sys.stderr)
        return 1

    head = heads[0]
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current = context.get_current_revision()

    if current is None:
        print(f"ERROR: database has no applied revision; head is {head!r}", file=sys.stderr)
        return 1

    if current != head:
        print(
            f"ERROR: database revision {current!r} does not match head {head!r}",
            file=sys.stderr,
        )
        return 1

    print(f"OK: database is at migration head {head!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
