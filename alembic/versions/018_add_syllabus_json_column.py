"""Add syllabus_json column to courses table

Revision ID: 018_add_syllabus_json
Revises: 017_add_enhanced_ai_features
Create Date: 2026-02-26

This migration adds a syllabus_json column to store structured syllabus data
matching the Syllabus Tool schema format.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018_add_syllabus_json'
down_revision = '017_add_enhanced_ai_features'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add syllabus_json column to courses table
    op.add_column('courses', sa.Column('syllabus_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove syllabus_json column from courses table
    op.drop_column('courses', 'syllabus_json')
