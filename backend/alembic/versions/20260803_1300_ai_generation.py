"""Add AI quiz generation tables.

Revision ID: 20260803_1300_ai_generation
Revises: 20260802_2000_host_accounts
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260803_1300_ai_generation"
down_revision = "20260802_2000_host_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_generation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(length=500), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("difficulty", sa.String(length=16), nullable=False, server_default="mixed"),
        sa.Column("question_kinds", sa.JSON(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("result_quiz_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["admins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["result_quiz_id"], ["quizzes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_generation_jobs_owner_id", "ai_generation_jobs", ["owner_id"])
    op.create_index("ix_ai_generation_jobs_status", "ai_generation_jobs", ["status"])
    op.create_index("ix_ai_generation_jobs_result_quiz_id", "ai_generation_jobs", ["result_quiz_id"])

    op.create_table(
        "ai_source_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extractor", sa.String(length=64), nullable=True),
        sa.Column("extracted_char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_text_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_source_files_job_id", "ai_source_files", ["job_id"])

    op.create_table(
        "ai_document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("section_hint", sa.String(length=255), nullable=True),
        sa.Column("embedding_json", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_generation_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_file_id"], ["ai_source_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "chunk_index", name="uq_ai_document_chunks_job_chunk"),
    )
    op.create_index("ix_ai_document_chunks_job_id", "ai_document_chunks", ["job_id"])

    op.create_table(
        "ai_generated_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("concepts_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "sort_order", name="uq_ai_generated_sections_job_sort"),
    )
    op.create_index("ix_ai_generated_sections_job_id", "ai_generated_sections", ["job_id"])

    op.create_table(
        "ai_generated_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("topic_label", sa.String(length=255), nullable=True),
        sa.Column("estimated_time_seconds", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("source_locator", sa.String(length=512), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_generation_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["ai_generated_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "sort_order", name="uq_ai_generated_questions_section_sort"),
    )
    op.create_index("ix_ai_generated_questions_job_id", "ai_generated_questions", ["job_id"])
    op.create_index("ix_ai_generated_questions_section_id", "ai_generated_questions", ["section_id"])

    op.create_table(
        "ai_source_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("locator", sa.String(length=1024), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_source_references_job_id", "ai_source_references", ["job_id"])


def downgrade() -> None:
    op.drop_table("ai_source_references")
    op.drop_table("ai_generated_questions")
    op.drop_table("ai_generated_sections")
    op.drop_table("ai_document_chunks")
    op.drop_table("ai_source_files")
    op.drop_table("ai_generation_jobs")
