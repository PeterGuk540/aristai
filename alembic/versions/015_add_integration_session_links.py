"""Add integration_session_links table to track imported sessions.

Revision ID: 015_integration_session_links
Revises: 014_multi_conn_integrations
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa


revision = "015_integration_session_links"
down_revision = "014_multi_conn_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_session_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_session_id", sa.String(length=255), nullable=False),
        sa.Column("external_course_id", sa.String(length=255), nullable=False),
        sa.Column("external_session_title", sa.String(length=500), nullable=True),
        sa.Column("week_number", sa.Integer(), nullable=True),
        sa.Column("source_connection_id", sa.Integer(), nullable=True),
        sa.Column("target_course_id", sa.Integer(), nullable=False),
        sa.Column("target_session_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_connection_id"],
            ["integration_provider_connections.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_course_id"],
            ["courses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_session_id"],
            ["sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_session_id",
            "target_course_id",
            "source_connection_id",
            name="uq_integration_session_link_provider_external_target",
        ),
    )
    op.create_index("ix_integration_session_links_id", "integration_session_links", ["id"], unique=False)
    op.create_index("ix_integration_session_links_provider", "integration_session_links", ["provider"], unique=False)
    op.create_index("ix_integration_session_links_external_session_id", "integration_session_links", ["external_session_id"], unique=False)
    op.create_index("ix_integration_session_links_external_course_id", "integration_session_links", ["external_course_id"], unique=False)
    op.create_index("ix_integration_session_links_source_connection_id", "integration_session_links", ["source_connection_id"], unique=False)
    op.create_index("ix_integration_session_links_target_course_id", "integration_session_links", ["target_course_id"], unique=False)
    op.create_index("ix_integration_session_links_target_session_id", "integration_session_links", ["target_session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_integration_session_links_target_session_id", table_name="integration_session_links")
    op.drop_index("ix_integration_session_links_target_course_id", table_name="integration_session_links")
    op.drop_index("ix_integration_session_links_source_connection_id", table_name="integration_session_links")
    op.drop_index("ix_integration_session_links_external_course_id", table_name="integration_session_links")
    op.drop_index("ix_integration_session_links_external_session_id", table_name="integration_session_links")
    op.drop_index("ix_integration_session_links_provider", table_name="integration_session_links")
    op.drop_index("ix_integration_session_links_id", table_name="integration_session_links")
    op.drop_table("integration_session_links")
