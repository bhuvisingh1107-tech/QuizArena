"""Add host profile fields and quiz ownership.

Revision ID: 20260802_2000_host_accounts
Revises: 20260731_1900_pause
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260802_2000_host_accounts"
down_revision = "20260731_1900_pause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admins") as batch:
        batch.add_column(
            sa.Column("email", sa.String(length=255), nullable=True),
        )
        batch.add_column(
            sa.Column(
                "name",
                sa.String(length=120),
                nullable=False,
                server_default="",
            ),
        )
        batch.create_index("ix_admins_email", ["email"], unique=True)

    with op.batch_alter_table("quizzes") as batch:
        batch.add_column(
            sa.Column("owner_id", sa.Uuid(), nullable=True),
        )
        batch.create_index("ix_quizzes_owner_id", ["owner_id"], unique=False)
        batch.create_foreign_key(
            "fk_quizzes_owner_id_admins",
            "admins",
            ["owner_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Backfill ownership to the earliest admin so existing quizzes remain usable.
    bind = op.get_bind()
    admin_id = bind.execute(sa.text("SELECT id FROM admins ORDER BY created_at ASC LIMIT 1")).scalar()
    if admin_id is not None:
        bind.execute(
            sa.text("UPDATE quizzes SET owner_id = :owner_id WHERE owner_id IS NULL"),
            {"owner_id": str(admin_id)},
        )


def downgrade() -> None:
    with op.batch_alter_table("quizzes") as batch:
        batch.drop_constraint("fk_quizzes_owner_id_admins", type_="foreignkey")
        batch.drop_index("ix_quizzes_owner_id")
        batch.drop_column("owner_id")

    with op.batch_alter_table("admins") as batch:
        batch.drop_index("ix_admins_email")
        batch.drop_column("name")
        batch.drop_column("email")
