"""Add instructor features tables for engagement tracking, breakout groups, templates, etc.

Revision ID: 012_instructor_features
Revises: 011_course_materials
Create Date: 2026-02-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_instructor_features'
down_revision = '011_course_materials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create engagement_level enum type (idempotent - check if exists first)
    engagement_level_enum = postgresql.ENUM(
        'highly_active', 'active', 'idle', 'disengaged', 'not_joined',
        name='engagement_level',
        create_type=False
    )

    # Create the enum type first (use DO block for idempotency)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE engagement_level AS ENUM ('highly_active', 'active', 'idle', 'disengaged', 'not_joined');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # 1. Student Engagements table
    op.create_table(
        'student_engagements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('engagement_level', engagement_level_enum, server_default='not_joined', nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('post_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('reply_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('poll_votes', sa.Integer(), server_default='0', nullable=True),
        sa.Column('avg_post_length', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('quality_posts', sa.Integer(), server_default='0', nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_student_engagements_id', 'student_engagements', ['id'], unique=False)
    op.create_index('ix_student_engagements_session_id', 'student_engagements', ['session_id'], unique=False)
    op.create_index('ix_student_engagements_user_id', 'student_engagements', ['user_id'], unique=False)
    # Unique constraint: one engagement record per user per session
    op.create_index('ix_student_engagements_session_user', 'student_engagements', ['session_id', 'user_id'], unique=True)

    # 2. Session Timers table
    op.create_table(
        'session_timers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('elapsed_seconds', sa.Integer(), server_default='0', nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('is_visible_to_students', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_session_timers_id', 'session_timers', ['id'], unique=False)
    op.create_index('ix_session_timers_session_id', 'session_timers', ['session_id'], unique=False)

    # 3. Breakout Groups table
    op.create_table(
        'breakout_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('topic', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_breakout_groups_id', 'breakout_groups', ['id'], unique=False)
    op.create_index('ix_breakout_groups_session_id', 'breakout_groups', ['session_id'], unique=False)

    # 4. Breakout Group Members table
    op.create_table(
        'breakout_group_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['breakout_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_breakout_group_members_id', 'breakout_group_members', ['id'], unique=False)
    op.create_index('ix_breakout_group_members_group_id', 'breakout_group_members', ['group_id'], unique=False)
    op.create_index('ix_breakout_group_members_user_id', 'breakout_group_members', ['user_id'], unique=False)

    # 5. Session Templates table
    op.create_table(
        'session_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('plan_json', sa.JSON(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('use_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_session_templates_id', 'session_templates', ['id'], unique=False)

    # 6. Pre-class Checkpoints table
    op.create_table(
        'preclass_checkpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('checkpoint_type', sa.String(length=50), server_default='reading', nullable=True),
        sa.Column('due_before_session', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_preclass_checkpoints_id', 'preclass_checkpoints', ['id'], unique=False)
    op.create_index('ix_preclass_checkpoints_session_id', 'preclass_checkpoints', ['session_id'], unique=False)

    # 7. Checkpoint Completions table
    op.create_table(
        'checkpoint_completions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('checkpoint_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['checkpoint_id'], ['preclass_checkpoints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_checkpoint_completions_id', 'checkpoint_completions', ['id'], unique=False)
    op.create_index('ix_checkpoint_completions_checkpoint_id', 'checkpoint_completions', ['checkpoint_id'], unique=False)
    op.create_index('ix_checkpoint_completions_user_id', 'checkpoint_completions', ['user_id'], unique=False)
    # Unique constraint: one completion per user per checkpoint
    op.create_index('ix_checkpoint_completions_checkpoint_user', 'checkpoint_completions', ['checkpoint_id', 'user_id'], unique=True)

    # 8. AI Response Drafts table
    op.create_table(
        'ai_response_drafts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('draft_content', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=True),
        sa.Column('instructor_edits', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_response_drafts_id', 'ai_response_drafts', ['id'], unique=False)
    op.create_index('ix_ai_response_drafts_post_id', 'ai_response_drafts', ['post_id'], unique=False)
    op.create_index('ix_ai_response_drafts_session_id', 'ai_response_drafts', ['session_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order (respect foreign key dependencies)
    op.drop_index('ix_ai_response_drafts_session_id', table_name='ai_response_drafts')
    op.drop_index('ix_ai_response_drafts_post_id', table_name='ai_response_drafts')
    op.drop_index('ix_ai_response_drafts_id', table_name='ai_response_drafts')
    op.drop_table('ai_response_drafts')

    op.drop_index('ix_checkpoint_completions_checkpoint_user', table_name='checkpoint_completions')
    op.drop_index('ix_checkpoint_completions_user_id', table_name='checkpoint_completions')
    op.drop_index('ix_checkpoint_completions_checkpoint_id', table_name='checkpoint_completions')
    op.drop_index('ix_checkpoint_completions_id', table_name='checkpoint_completions')
    op.drop_table('checkpoint_completions')

    op.drop_index('ix_preclass_checkpoints_session_id', table_name='preclass_checkpoints')
    op.drop_index('ix_preclass_checkpoints_id', table_name='preclass_checkpoints')
    op.drop_table('preclass_checkpoints')

    op.drop_index('ix_session_templates_id', table_name='session_templates')
    op.drop_table('session_templates')

    op.drop_index('ix_breakout_group_members_user_id', table_name='breakout_group_members')
    op.drop_index('ix_breakout_group_members_group_id', table_name='breakout_group_members')
    op.drop_index('ix_breakout_group_members_id', table_name='breakout_group_members')
    op.drop_table('breakout_group_members')

    op.drop_index('ix_breakout_groups_session_id', table_name='breakout_groups')
    op.drop_index('ix_breakout_groups_id', table_name='breakout_groups')
    op.drop_table('breakout_groups')

    op.drop_index('ix_session_timers_session_id', table_name='session_timers')
    op.drop_index('ix_session_timers_id', table_name='session_timers')
    op.drop_table('session_timers')

    op.drop_index('ix_student_engagements_session_user', table_name='student_engagements')
    op.drop_index('ix_student_engagements_user_id', table_name='student_engagements')
    op.drop_index('ix_student_engagements_session_id', table_name='student_engagements')
    op.drop_index('ix_student_engagements_id', table_name='student_engagements')
    op.drop_table('student_engagements')

    # Drop the enum type
    op.execute("DROP TYPE engagement_level")
