"""add lesson_type to lessons

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'lessons',
        sa.Column('lesson_type', sa.String(20), nullable=False, server_default='standard'),
    )


def downgrade():
    op.drop_column('lessons', 'lesson_type')
