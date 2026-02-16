"""Add Canvas push and provider connection tables.

Revision ID: 014_canvas_push_tables
Revises: 013_integrations_tables
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "014_canvas_push_tables"
down_revision = "013_integrations_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create integration_provider_connections table
    op.create_table(
        "integration_provider_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("api_base_url", sa.String(length=500), nullable=False),
        sa.Column("api_token_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=30), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "label", name="uq_integration_provider_connection_provider_label"),
    )
    op.create_index("ix_integration_provider_connections_id", "integration_provider_connections", ["id"], unique=False)
    op.create_index("ix_integration_provider_connections_provider", "integration_provider_connections", ["provider"], unique=False)
    op.create_index("ix_integration_provider_connections_created_by", "integration_provider_connections", ["created_by"], unique=False)

    # Create integration_canvas_pushes table
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
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["integration_provider_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_canvas_pushes_id", "integration_canvas_pushes", ["id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_session_id", "integration_canvas_pushes", ["session_id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_connection_id", "integration_canvas_pushes", ["connection_id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_external_course_id", "integration_canvas_pushes", ["external_course_id"], unique=False)
    op.create_index("ix_integration_canvas_pushes_triggered_by", "integration_canvas_pushes", ["triggered_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_integration_canvas_pushes_triggered_by", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_external_course_id", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_connection_id", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_session_id", table_name="integration_canvas_pushes")
    op.drop_index("ix_integration_canvas_pushes_id", table_name="integration_canvas_pushes")
    op.drop_table("integration_canvas_pushes")

    op.drop_index("ix_integration_provider_connections_created_by", table_name="integration_provider_connections")
    op.drop_index("ix_integration_provider_connections_provider", table_name="integration_provider_connections")
    op.drop_index("ix_integration_provider_connections_id", table_name="integration_provider_connections")
    op.drop_table("integration_provider_connections")
