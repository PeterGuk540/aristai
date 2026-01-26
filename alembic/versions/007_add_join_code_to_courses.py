"""Add join_code to courses table

Revision ID: 007_add_join_code
Revises: 006_set_instructor_role
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa
import secrets
import string

# revision identifiers
revision = '007_add_join_code'
down_revision = '006_set_instructor_role'
branch_labels = None
depends_on = None


def generate_join_code(length: int = 8) -> str:
    """Generate a random alphanumeric join code."""
    alphabet = string.ascii_uppercase + string.digits
    # Exclude confusing characters like 0, O, I, 1
    alphabet = alphabet.replace('0', '').replace('O', '').replace('I', '').replace('1', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def upgrade() -> None:
    # Add join_code column
    op.add_column(
        'courses',
        sa.Column('join_code', sa.String(20), nullable=True)
    )

    # Create unique index on join_code
    op.create_index('ix_courses_join_code', 'courses', ['join_code'], unique=True)

    # Generate join codes for existing courses
    connection = op.get_bind()
    courses = connection.execute(sa.text("SELECT id FROM courses")).fetchall()

    used_codes = set()
    for course in courses:
        code = generate_join_code()
        while code in used_codes:
            code = generate_join_code()
        used_codes.add(code)
        connection.execute(
            sa.text("UPDATE courses SET join_code = :code WHERE id = :id"),
            {"code": code, "id": course[0]}
        )


def downgrade() -> None:
    op.drop_index('ix_courses_join_code', table_name='courses')
    op.drop_column('courses', 'join_code')
