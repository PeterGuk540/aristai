"""Add course_materials table for S3 file uploads

Revision ID: 008_course_materials
Revises: 007_add_join_code_to_courses
Create Date: 2025-02-08
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_course_materials'
down_revision = '007_add_join_code_to_courses'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'course_materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('s3_key', sa.String(length=1000), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('content_type', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=True),
        sa.Column('replaced_material_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['replaced_material_id'], ['course_materials.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_course_materials_id'), 'course_materials', ['id'], unique=False)
    op.create_index(op.f('ix_course_materials_course_id'), 'course_materials', ['course_id'], unique=False)
    op.create_index(op.f('ix_course_materials_session_id'), 'course_materials', ['session_id'], unique=False)
    op.create_index(op.f('ix_course_materials_s3_key'), 'course_materials', ['s3_key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_course_materials_s3_key'), table_name='course_materials')
    op.drop_index(op.f('ix_course_materials_session_id'), table_name='course_materials')
    op.drop_index(op.f('ix_course_materials_course_id'), table_name='course_materials')
    op.drop_index(op.f('ix_course_materials_id'), table_name='course_materials')
    op.drop_table('course_materials')
