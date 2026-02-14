"""Add provider connection configs and connection-aware integration keys.

Revision ID: 014_multi_connection_integrations
Revises: 013_integrations_tables
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa


revision = "014_multi_connection_integrations"
down_revision = "013_integrations_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    op.add_column("integration_course_mappings", sa.Column("source_connection_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_integration_course_mappings_source_connection_id",
        "integration_course_mappings",
        ["source_connection_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_integration_course_mappings_source_connection_id",
        "integration_course_mappings",
        "integration_provider_connections",
        ["source_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("uq_integration_course_mapping", "integration_course_mappings", type_="unique")
    op.create_unique_constraint(
        "uq_integration_course_mapping",
        "integration_course_mappings",
        ["provider", "external_course_id", "target_course_id", "source_connection_id"],
    )

    op.add_column("integration_sync_jobs", sa.Column("source_connection_id", sa.Integer(), nullable=True))
    op.create_index("ix_integration_sync_jobs_source_connection_id", "integration_sync_jobs", ["source_connection_id"], unique=False)
    op.create_foreign_key(
        "fk_integration_sync_jobs_source_connection_id",
        "integration_sync_jobs",
        "integration_provider_connections",
        ["source_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("integration_material_links", sa.Column("source_connection_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_integration_material_links_source_connection_id",
        "integration_material_links",
        ["source_connection_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_integration_material_links_source_connection_id",
        "integration_material_links",
        "integration_provider_connections",
        ["source_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("uq_integration_material_link_provider_external_target", "integration_material_links", type_="unique")
    op.create_unique_constraint(
        "uq_integration_material_link_provider_external_target",
        "integration_material_links",
        ["provider", "external_material_id", "target_course_id", "target_session_id", "source_connection_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_integration_material_link_provider_external_target", "integration_material_links", type_="unique")
    op.create_unique_constraint(
        "uq_integration_material_link_provider_external_target",
        "integration_material_links",
        ["provider", "external_material_id", "target_course_id", "target_session_id"],
    )
    op.drop_constraint("fk_integration_material_links_source_connection_id", "integration_material_links", type_="foreignkey")
    op.drop_index("ix_integration_material_links_source_connection_id", table_name="integration_material_links")
    op.drop_column("integration_material_links", "source_connection_id")

    op.drop_constraint("fk_integration_sync_jobs_source_connection_id", "integration_sync_jobs", type_="foreignkey")
    op.drop_index("ix_integration_sync_jobs_source_connection_id", table_name="integration_sync_jobs")
    op.drop_column("integration_sync_jobs", "source_connection_id")

    op.drop_constraint("uq_integration_course_mapping", "integration_course_mappings", type_="unique")
    op.create_unique_constraint(
        "uq_integration_course_mapping",
        "integration_course_mappings",
        ["provider", "external_course_id", "target_course_id"],
    )
    op.drop_constraint("fk_integration_course_mappings_source_connection_id", "integration_course_mappings", type_="foreignkey")
    op.drop_index("ix_integration_course_mappings_source_connection_id", table_name="integration_course_mappings")
    op.drop_column("integration_course_mappings", "source_connection_id")

    op.drop_index("ix_integration_provider_connections_provider", table_name="integration_provider_connections")
    op.drop_index("ix_integration_provider_connections_id", table_name="integration_provider_connections")
    op.drop_table("integration_provider_connections")
