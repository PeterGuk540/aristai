"""Add auth_provider and cognito_sub to users table

Revision ID: 005_add_auth_provider
Revises: 004_add_enrollments
Create Date: 2026-01-24
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '005_add_auth_provider'
down_revision = '004_add_enrollments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the auth_provider enum type
    auth_provider_enum = sa.Enum('cognito', 'google', name='auth_provider')
    auth_provider_enum.create(op.get_bind(), checkfirst=True)

    # Add auth_provider column with default 'cognito' for existing users
    op.add_column(
        'users',
        sa.Column('auth_provider', auth_provider_enum, nullable=False, server_default='cognito')
    )

    # Add cognito_sub column for storing the Cognito user sub ID
    op.add_column(
        'users',
        sa.Column('cognito_sub', sa.String(255), nullable=True)
    )

    # Create index on cognito_sub for faster lookups
    op.create_index('ix_users_cognito_sub', 'users', ['cognito_sub'])


def downgrade() -> None:
    op.drop_index('ix_users_cognito_sub', table_name='users')
    op.drop_column('users', 'cognito_sub')
    op.drop_column('users', 'auth_provider')

    # Drop the enum type
    auth_provider_enum = sa.Enum('cognito', 'google', name='auth_provider')
    auth_provider_enum.drop(op.get_bind(), checkfirst=True)
