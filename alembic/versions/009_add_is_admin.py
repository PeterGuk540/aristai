"""Add is_admin column to users

Revision ID: 009_add_is_admin
Revises: 008_add_instructor_request
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '009_add_is_admin'
down_revision = '008_add_instructor_request'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_admin column with default False
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false')
    )

    # Set user id=3 (aojieju@gmail.com, cognito, instructor) as admin
    op.execute("UPDATE users SET is_admin = true WHERE id = 3")


def downgrade() -> None:
    op.drop_column('users', 'is_admin')
