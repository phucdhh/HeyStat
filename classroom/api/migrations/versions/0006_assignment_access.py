"""Add teacher-controlled assignment and file access."""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    # Preserve access to existing coursework; new exams start closed in the API.
    op.add_column('assignments', sa.Column('is_open', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('class_files', sa.Column('student_access', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column('class_files', 'student_access')
    op.drop_column('assignments', 'is_open')
