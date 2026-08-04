"""Audit export fields: broadcast_at, answer_order, streak before/after.

Revision ID: 20260804_1830_audit_export
Revises: 20260804_1730_response_ranks
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260804_1830_audit_export"
down_revision = "20260804_1730_response_ranks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("session_questions") as batch:
        batch.add_column(sa.Column("broadcast_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("responses") as batch:
        batch.add_column(sa.Column("answer_order", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("streak_before", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("streak_after", sa.Integer(), nullable=True))

    # Backfill broadcast_at from opened_at for existing rows.
    op.execute(
        sa.text(
            "UPDATE session_questions SET broadcast_at = opened_at "
            "WHERE broadcast_at IS NULL AND opened_at IS NOT NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("responses") as batch:
        batch.drop_column("streak_after")
        batch.drop_column("streak_before")
        batch.drop_column("answer_order")
    with op.batch_alter_table("session_questions") as batch:
        batch.drop_column("broadcast_at")
