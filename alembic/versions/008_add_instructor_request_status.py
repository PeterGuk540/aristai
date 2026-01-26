"""Add instructor_request_status and instructor_request_date to users

Revision ID: 008_add_instructor_request
Revises: 007_add_join_code
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '008_add_instructor_request'
down_revision = '007_add_join_code'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the enum type first
    instructor_request_status = sa.Enum(
        'none', 'pending', 'approved', 'rejected',
        name='instructor_request_status'
    )
    instructor_request_status.create(op.get_bind(), checkfirst=True)

    # Add instructor_request_status column
    op.add_column(
        'users',
        sa.Column(
            'instructor_request_status',
            sa.Enum('none', 'pending', 'approved', 'rejected', name='instructor_request_status'),
            nullable=False,
            server_default='none'
        )
    )

    # Add instructor_request_date column
    op.add_column(
        'users',
        sa.Column('instructor_request_date', sa.DateTime(timezone=True), nullable=True)
    )

    # Also add 'microsoft' to auth_provider enum if not exists
    # This is done via raw SQL for PostgreSQL
    op.execute("ALTER TYPE auth_provider ADD VALUE IF NOT EXISTS 'microsoft'")


def downgrade() -> None:
    op.drop_column('users', 'instructor_request_date')
    op.drop_column('users', 'instructor_request_status')
    # Note: Dropping enum types requires careful handling, skipped for safety
