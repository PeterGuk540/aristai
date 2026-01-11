"""Add pinned column to posts table

Revision ID: 002_add_pinned
Revises: 001_initial
Create Date: 2025-01-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_add_pinned'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pinned column to posts table with default False
    op.add_column(
        'posts',
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade() -> None:
    op.drop_column('posts', 'pinned')
