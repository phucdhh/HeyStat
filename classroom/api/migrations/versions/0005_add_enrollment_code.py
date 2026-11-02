"""add enrollment_code to classes

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'classes',
        sa.Column('enrollment_code', sa.String(16), nullable=True),
    )
    op.create_unique_constraint('uq_classes_enrollment_code', 'classes', ['enrollment_code'])


def downgrade():
    op.drop_constraint('uq_classes_enrollment_code', 'classes', type_='unique')
    op.drop_column('classes', 'enrollment_code')
