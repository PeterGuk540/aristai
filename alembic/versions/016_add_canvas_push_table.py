"""Add integration_canvas_pushes table to track Canvas push operations.

Revision ID: 016_canvas_push
Revises: 015_integration_session_links
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa


revision = "016_canvas_push"
down_revision = "015_integration_session_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_canvas_pushes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("external_course_id", sa.String(length=255), nullable=False),
        sa.Column("push_type", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.String(length=20), nullable=True),
        sa.Column("execution_time_seconds", sa.String(length=20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["integration_provider_connections.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_canvas_pushes_id", "integration_canvas_pushes", ["id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_session_id", "integration_canvas_pushes", ["session_id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_connection_id", "integration_canvas_pushes", ["connection_id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_external_course_id", "integration_canvas_pushes", ["external_course_id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_status", "integration_canvas_pushes", ["status"], unique=False)
    op.create_index("ix_integration_canvas_pushes_triggered_by", "integration_canvas_pushes", ["triggered_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_integration_canvas_pushes_triggered_by", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_status", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_external_course_id", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_connection_id", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_session_id", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_id", table_name="integration_canvas_pushes")
    op.drop_table("integration_canvas_pushes")
