"""Scheduled start time for assignments.

A teacher can set "Giờ bắt đầu". Until that moment the assignment behaves like
a closed one for students: they cannot see the brief, open the dataset, start a
jamovi session or submit. NULL means no restriction, which preserves the
behaviour of every existing assignment.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-25
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'assignments',
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column('assignments', 'start_at')
