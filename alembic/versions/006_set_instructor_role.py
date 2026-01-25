"""Set aojieju@gmail.com (cognito login) as instructor

Revision ID: 006_set_instructor_role
Revises: 005_add_auth_provider
Create Date: 2026-01-24
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '006_set_instructor_role'
down_revision = '005_add_auth_provider'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set the cognito user (email/password login) with aojieju@gmail.com as instructor
    # This keeps the Google login with the same email as student
    op.execute(
        """
        UPDATE users
        SET role = 'instructor'
        WHERE email = 'aojieju@gmail.com'
        AND auth_provider = 'cognito'
        """
    )


def downgrade() -> None:
    # Revert to student role
    op.execute(
        """
        UPDATE users
        SET role = 'student'
        WHERE email = 'aojieju@gmail.com'
        AND auth_provider = 'cognito'
        """
    )
