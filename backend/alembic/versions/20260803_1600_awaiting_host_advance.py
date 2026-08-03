"""Add awaiting_host_advance and session_events.

Revision ID: 20260803_1600_awaiting_host_advance
Revises: 20260803_1300_ai_generation
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260803_1600_awaiting_host_advance"
down_revision = "20260803_1300_ai_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("live_rooms") as batch:
        batch.add_column(
            sa.Column(
                "awaiting_host_advance",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_table(
        "session_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("live_room_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["live_room_id"],
            ["live_rooms.id"],
            name=op.f("fk_session_events_live_room_id_live_rooms"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_events")),
    )
    op.create_index(
        "ix_session_events_room_created",
        "session_events",
        ["live_room_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_session_events_room_created", table_name="session_events")
    op.drop_table("session_events")

    with op.batch_alter_table("live_rooms") as batch:
        batch.drop_column("awaiting_host_advance")
