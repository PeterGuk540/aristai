"""Add LMS integration persistence tables.

Revision ID: 013_integrations_tables
Revises: 012_instructor_features
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "013_integrations_tables"
down_revision = "012_instructor_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("provider_user_id", sa.String(length=255), nullable=True),
        sa.Column("provider_user_name", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "user_id", name="uq_integration_connection_provider_user"),
    )
    op.create_index("ix_integration_connections_id", "integration_connections", ["id"], unique=False)
    op.create_index("ix_integration_connections_provider", "integration_connections", ["provider"], unique=False)
    op.create_index("ix_integration_connections_user_id", "integration_connections", ["user_id"], unique=False)

    op.create_table(
        "integration_course_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_course_id", sa.String(length=255), nullable=False),
        sa.Column("external_course_name", sa.String(length=500), nullable=True),
        sa.Column("target_course_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["target_course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_course_id", "target_course_id", name="uq_integration_course_mapping"),
    )
    op.create_index("ix_integration_course_mappings_id", "integration_course_mappings", ["id"], unique=False)
    op.create_index("ix_integration_course_mappings_provider", "integration_course_mappings", ["provider"], unique=False)
    op.create_index("ix_integration_course_mappings_external_course_id", "integration_course_mappings", ["external_course_id"], unique=False)
    op.create_index("ix_integration_course_mappings_target_course_id", "integration_course_mappings", ["target_course_id"], unique=False)

    op.create_table(
        "integration_sync_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("source_course_external_id", sa.String(length=255), nullable=False),
        sa.Column("target_course_id", sa.Integer(), nullable=False),
        sa.Column("target_session_id", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("requested_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["target_course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_sync_jobs_id", "integration_sync_jobs", ["id"], unique=False)
    op.create_index("ix_integration_sync_jobs_provider", "integration_sync_jobs", ["provider"], unique=False)
    op.create_index("ix_integration_sync_jobs_source_course_external_id", "integration_sync_jobs", ["source_course_external_id"], unique=False)
    op.create_index("ix_integration_sync_jobs_target_course_id", "integration_sync_jobs", ["target_course_id"], unique=False)
    op.create_index("ix_integration_sync_jobs_target_session_id", "integration_sync_jobs", ["target_session_id"], unique=False)
    op.create_index("ix_integration_sync_jobs_triggered_by", "integration_sync_jobs", ["triggered_by"], unique=False)

    op.create_table(
        "integration_sync_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("external_material_id", sa.String(length=255), nullable=False),
        sa.Column("external_material_name", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("course_material_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["integration_sync_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_material_id"], ["course_materials.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_sync_items_id", "integration_sync_items", ["id"], unique=False)
    op.create_index("ix_integration_sync_items_job_id", "integration_sync_items", ["job_id"], unique=False)
    op.create_index("ix_integration_sync_items_external_material_id", "integration_sync_items", ["external_material_id"], unique=False)
    op.create_index("ix_integration_sync_items_course_material_id", "integration_sync_items", ["course_material_id"], unique=False)

    op.create_table(
        "integration_material_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_material_id", sa.String(length=255), nullable=False),
        sa.Column("external_course_id", sa.String(length=255), nullable=False),
        sa.Column("target_course_id", sa.Integer(), nullable=False),
        sa.Column("target_session_id", sa.Integer(), nullable=True),
        sa.Column("course_material_id", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["target_course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["course_material_id"], ["course_materials.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_material_id",
            "target_course_id",
            "target_session_id",
            name="uq_integration_material_link_provider_external_target",
        ),
    )
    op.create_index("ix_integration_material_links_id", "integration_material_links", ["id"], unique=False)
    op.create_index("ix_integration_material_links_provider", "integration_material_links", ["provider"], unique=False)
    op.create_index("ix_integration_material_links_external_material_id", "integration_material_links", ["external_material_id"], unique=False)
    op.create_index("ix_integration_material_links_external_course_id", "integration_material_links", ["external_course_id"], unique=False)
    op.create_index("ix_integration_material_links_target_course_id", "integration_material_links", ["target_course_id"], unique=False)
    op.create_index("ix_integration_material_links_target_session_id", "integration_material_links", ["target_session_id"], unique=False)
    op.create_index("ix_integration_material_links_course_material_id", "integration_material_links", ["course_material_id"], unique=False)
    op.create_index("ix_integration_material_links_checksum_sha256", "integration_material_links", ["checksum_sha256"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_integration_material_links_checksum_sha256", table_name="integration_material_links")
    op.drop_index("ix_integration_material_links_course_material_id", table_name="integration_material_links")
    op.drop_index("ix_integration_material_links_target_session_id", table_name="integration_material_links")
    op.drop_index("ix_integration_material_links_target_course_id", table_name="integration_material_links")
    op.drop_index("ix_integration_material_links_external_course_id", table_name="integration_material_links")
    op.drop_index("ix_integration_material_links_external_material_id", table_name="integration_material_links")
    op.drop_index("ix_integration_material_links_provider", table_name="integration_material_links")
    op.drop_index("ix_integration_material_links_id", table_name="integration_material_links")
    op.drop_table("integration_material_links")

    op.drop_index("ix_integration_sync_items_course_material_id", table_name="integration_sync_items")
    op.drop_index("ix_integration_sync_items_external_material_id", table_name="integration_sync_items")
    op.drop_index("ix_integration_sync_items_job_id", table_name="integration_sync_items")
    op.drop_index("ix_integration_sync_items_id", table_name="integration_sync_items")
    op.drop_table("integration_sync_items")

    op.drop_index("ix_integration_sync_jobs_triggered_by", table_name="integration_sync_jobs")
    op.drop_index("ix_integration_sync_jobs_target_session_id", table_name="integration_sync_jobs")
    op.drop_index("ix_integration_sync_jobs_target_course_id", table_name="integration_sync_jobs")
    op.drop_index("ix_integration_sync_jobs_source_course_external_id", table_name="integration_sync_jobs")
    op.drop_index("ix_integration_sync_jobs_provider", table_name="integration_sync_jobs")
    op.drop_index("ix_integration_sync_jobs_id", table_name="integration_sync_jobs")
    op.drop_table("integration_sync_jobs")

    op.drop_index("ix_integration_course_mappings_target_course_id", table_name="integration_course_mappings")
    op.drop_index("ix_integration_course_mappings_external_course_id", table_name="integration_course_mappings")
    op.drop_index("ix_integration_course_mappings_provider", table_name="integration_course_mappings")
    op.drop_index("ix_integration_course_mappings_id", table_name="integration_course_mappings")
    op.drop_table("integration_course_mappings")

    op.drop_index("ix_integration_connections_user_id", table_name="integration_connections")
    op.drop_index("ix_integration_connections_provider", table_name="integration_connections")
    op.drop_index("ix_integration_connections_id", table_name="integration_connections")
    op.drop_table("integration_connections")
