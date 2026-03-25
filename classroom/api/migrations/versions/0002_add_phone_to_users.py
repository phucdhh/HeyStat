"""add phone to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('phone', sa.String(50), nullable=True))


def downgrade():
    op.drop_column('users', 'phone')
