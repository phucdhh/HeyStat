"""Release datasets attached to open assignments.

A file can be locked independently of its assignment. Before this guard that
combination was reachable and students could not open the dataset for a piece
of work the teacher had opened.
"""
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE class_files SET student_access = true
        WHERE id IN (
            SELECT file_id FROM assignments
            WHERE is_open AND file_id IS NOT NULL
        )
        """
    )


def downgrade():
    # The previous per-file choice cannot be reconstructed.
    pass
