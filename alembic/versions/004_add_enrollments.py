"""Add enrollments table for course enrollment tracking

Revision ID: 004_add_enrollments
Revises: 003_add_observability
Create Date: 2025-01-18
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '004_add_enrollments'
down_revision = '003_add_observability'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'course_id', name='unique_enrollment')
    )
    op.create_index('ix_enrollments_id', 'enrollments', ['id'])
    op.create_index('ix_enrollments_user_id', 'enrollments', ['user_id'])
    op.create_index('ix_enrollments_course_id', 'enrollments', ['course_id'])


def downgrade() -> None:
    op.drop_index('ix_enrollments_course_id', table_name='enrollments')
    op.drop_index('ix_enrollments_user_id', table_name='enrollments')
    op.drop_index('ix_enrollments_id', table_name='enrollments')
    op.drop_table('enrollments')
