"""Add session_questions.opened_at for authoritative question timers."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260731_1845_opened_at"
down_revision: Union[str, Sequence[str], None] = "20260731_1745_quiz_builder"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("session_questions") as batch:
        batch.add_column(sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("session_questions") as batch:
        batch.drop_column("opened_at")
