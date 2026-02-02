"""Add voice_audits table

Revision ID: 010_add_voice_audit
Revises: 009_add_is_admin
Create Date: 2026-02-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '010_add_voice_audit'
down_revision = '009_add_is_admin'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'voice_audits',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('transcript_hash', sa.String(64), nullable=False),
        sa.Column('plan_json', sa.JSON(), nullable=False),
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('voice_audits')
