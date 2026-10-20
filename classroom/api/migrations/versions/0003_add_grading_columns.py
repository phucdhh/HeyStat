"""add grading criteria, answer key and auto-grade result

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('assignments', sa.Column('answer_key', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('assignments', sa.Column('grading_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('submissions', sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('submissions', sa.Column('auto_grade', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('submissions', 'auto_grade')
    op.drop_column('submissions', 'answers')
    op.drop_column('assignments', 'grading_config')
    op.drop_column('assignments', 'answer_key')
