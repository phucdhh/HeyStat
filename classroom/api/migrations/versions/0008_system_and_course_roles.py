"""System roles and course-level roles.

The platform gains a 'moderator' role, enrollments gain a per-class role so a
teacher can appoint an assistant, and teacher-role requests get a table for
admins to approve — the spec requires an admin to unlock class creation so a
registered account cannot spam courses.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    # 'guest' is deliberately not a row: it is the absence of an account.
    op.execute("INSERT INTO roles (id, name) VALUES (4,'moderator') ON CONFLICT (id) DO NOTHING")

    op.add_column(
        'enrollments',
        sa.Column('role', sa.String(20), nullable=False, server_default='student'),
    )
    op.create_check_constraint(
        'chk_enrollment_role', 'enrollments', "role IN ('student','assistant')"
    )

    op.create_table(
        'teacher_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('institution', sa.String(255)),
        sa.Column('reason', sa.Text),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True)),
        sa.Column('review_note', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_teacher_requests_user_id', 'teacher_requests', ['user_id'])
    op.create_index('ix_teacher_requests_status', 'teacher_requests', ['status'])


def downgrade():
    op.drop_index('ix_teacher_requests_status', table_name='teacher_requests')
    op.drop_index('ix_teacher_requests_user_id', table_name='teacher_requests')
    op.drop_table('teacher_requests')
    op.drop_constraint('chk_enrollment_role', 'enrollments', type_='check')
    op.drop_column('enrollments', 'role')
    op.execute("DELETE FROM user_roles WHERE role_id = 4")
    op.execute("DELETE FROM roles WHERE id = 4")
