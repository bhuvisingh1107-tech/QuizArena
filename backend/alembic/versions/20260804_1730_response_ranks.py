"""Add rank_before/rank_after on responses for export audit.

Revision ID: 20260804_1730_response_ranks
Revises: 20260803_1600_host_advance
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260804_1730_response_ranks"
down_revision = "20260803_1600_host_advance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("responses") as batch:
        batch.add_column(sa.Column("rank_before", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("rank_after", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("responses") as batch:
        batch.drop_column("rank_after")
        batch.drop_column("rank_before")
