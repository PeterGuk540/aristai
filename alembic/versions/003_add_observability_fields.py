"""Add observability fields for Milestone 6

Adds execution_time, token_usage, cost, error tracking to:
- reports
- interventions
- sessions (planning)

Revision ID: 003_add_observability
Revises: 002_add_pinned
Create Date: 2025-01-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '003_add_observability'
down_revision = '002_add_pinned'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add observability fields to reports table
    op.add_column('reports', sa.Column('execution_time_seconds', sa.Float(), nullable=True))
    op.add_column('reports', sa.Column('total_tokens', sa.Integer(), nullable=True))
    op.add_column('reports', sa.Column('prompt_tokens', sa.Integer(), nullable=True))
    op.add_column('reports', sa.Column('completion_tokens', sa.Integer(), nullable=True))
    op.add_column('reports', sa.Column('estimated_cost_usd', sa.Float(), nullable=True))
    op.add_column('reports', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('retry_count', sa.Integer(), server_default='0'))
    op.add_column('reports', sa.Column('used_fallback', sa.Integer(), server_default='0'))

    # Add observability fields to interventions table
    op.add_column('interventions', sa.Column('execution_time_seconds', sa.Float(), nullable=True))
    op.add_column('interventions', sa.Column('total_tokens', sa.Integer(), nullable=True))
    op.add_column('interventions', sa.Column('prompt_tokens', sa.Integer(), nullable=True))
    op.add_column('interventions', sa.Column('completion_tokens', sa.Integer(), nullable=True))
    op.add_column('interventions', sa.Column('estimated_cost_usd', sa.Float(), nullable=True))
    op.add_column('interventions', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('interventions', sa.Column('used_fallback', sa.Integer(), server_default='0'))
    op.add_column('interventions', sa.Column('posts_analyzed', sa.Integer(), nullable=True))

    # Add observability fields to sessions table (for planning)
    op.add_column('sessions', sa.Column('planning_execution_time_seconds', sa.Float(), nullable=True))
    op.add_column('sessions', sa.Column('planning_total_tokens', sa.Integer(), nullable=True))
    op.add_column('sessions', sa.Column('planning_estimated_cost_usd', sa.Float(), nullable=True))
    op.add_column('sessions', sa.Column('planning_used_fallback', sa.Integer(), server_default='0'))


def downgrade() -> None:
    # Remove from sessions
    op.drop_column('sessions', 'planning_used_fallback')
    op.drop_column('sessions', 'planning_estimated_cost_usd')
    op.drop_column('sessions', 'planning_total_tokens')
    op.drop_column('sessions', 'planning_execution_time_seconds')

    # Remove from interventions
    op.drop_column('interventions', 'posts_analyzed')
    op.drop_column('interventions', 'used_fallback')
    op.drop_column('interventions', 'error_message')
    op.drop_column('interventions', 'estimated_cost_usd')
    op.drop_column('interventions', 'completion_tokens')
    op.drop_column('interventions', 'prompt_tokens')
    op.drop_column('interventions', 'total_tokens')
    op.drop_column('interventions', 'execution_time_seconds')

    # Remove from reports
    op.drop_column('reports', 'used_fallback')
    op.drop_column('reports', 'retry_count')
    op.drop_column('reports', 'error_message')
    op.drop_column('reports', 'estimated_cost_usd')
    op.drop_column('reports', 'completion_tokens')
    op.drop_column('reports', 'prompt_tokens')
    op.drop_column('reports', 'total_tokens')
    op.drop_column('reports', 'execution_time_seconds')
