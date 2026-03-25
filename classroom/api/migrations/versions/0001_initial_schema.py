"""Initial schema – all tables

Revision ID: 0001
Revises: 
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # roles
    op.create_table(
        'roles',
        sa.Column('id', sa.SmallInteger(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.execute("INSERT INTO roles (id, name) VALUES (1,'admin'),(2,'teacher'),(3,'user')")

    # users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255)),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('avatar_url', sa.String(500)),
        sa.Column('provider', sa.String(50), server_default='local'),
        sa.Column('provider_id', sa.String(255)),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # user_roles
    op.create_table(
        'user_roles',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', sa.SmallInteger(), nullable=False),
        sa.Column('granted_by', postgresql.UUID(as_uuid=True)),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'role_id'),
    )

    # system_settings
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Text()),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('key'),
    )
    op.execute("""
        INSERT INTO system_settings (key, value) VALUES
        ('max_file_size_mb', '50'),
        ('max_user_files', '100'),
        ('max_user_storage_mb', '500'),
        ('allowed_file_types', 'csv,xlsx,xls,sav,sas7bdat,ods,omv'),
        ('maintenance_mode', 'false')
    """)

    # classes
    op.create_table(
        'classes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('enrollment_key', sa.String(100), nullable=False),
        sa.Column('max_students', sa.Integer(), server_default='200'),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('ends_at > starts_at', name='chk_dates'),
    )

    # enrollments
    op.create_table(
        'enrollments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('class_id', 'user_id', name='uq_enrollment'),
    )

    # class_files
    op.create_table(
        'class_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True)),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.BigInteger()),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # assignments
    op.create_table(
        'assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True)),
        sa.Column('assignment_type', sa.String(20), server_default='homework'),
        sa.Column('max_score', sa.Numeric(5, 2), server_default='10.00'),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=False),
        sa.Column('allow_resubmit', sa.Boolean(), server_default='true'),
        sa.Column('group_size', sa.SmallInteger(), server_default='1'),
        sa.Column('allow_sharing', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['class_files.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("NOT (assignment_type = 'exam' AND allow_sharing = TRUE)", name='chk_exam_no_sharing'),
        sa.CheckConstraint("NOT (assignment_type = 'exam' AND allow_resubmit = TRUE)", name='chk_exam_no_resubmit'),
    )

    # assignment_groups
    op.create_table(
        'assignment_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('assignment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('group_name', sa.String(100)),
        sa.Column('session_path', sa.String(500)),
        sa.Column('leader_id', postgresql.UUID(as_uuid=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['leader_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # assignment_group_members
    op.create_table(
        'assignment_group_members',
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['group_id'], ['assignment_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('group_id', 'user_id'),
    )

    # submissions
    op.create_table(
        'submissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('assignment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_snapshot', postgresql.JSONB()),
        sa.Column('file_path', sa.String(500)),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('is_final', sa.Boolean(), server_default='false'),
        sa.Column('score', sa.Numeric(5, 2)),
        sa.Column('feedback', sa.Text()),
        sa.Column('graded_by', postgresql.UUID(as_uuid=True)),
        sa.Column('graded_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['graded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # notifications
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text()),
        sa.Column('metadata', postgresql.JSONB()),
        sa.Column('is_read', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # lessons
    op.create_table(
        'lessons',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text()),
        sa.Column('sort_order', sa.SmallInteger(), server_default='0'),
        sa.Column('is_published', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # lesson_resources
    op.create_table(
        'lesson_resources',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('lesson_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_type', sa.String(20), nullable=False),
        sa.Column('title', sa.String(255)),
        sa.Column('url', sa.String(1000)),
        sa.Column('file_id', postgresql.UUID(as_uuid=True)),
        sa.Column('sort_order', sa.SmallInteger(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['file_id'], ['class_files.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "(url IS NOT NULL AND file_id IS NULL) OR (url IS NULL AND file_id IS NOT NULL)",
            name='chk_resource_source',
        ),
    )

    # quizzes
    op.create_table(
        'quizzes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lesson_id', postgresql.UUID(as_uuid=True)),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('time_limit_min', sa.SmallInteger()),
        sa.Column('max_attempts', sa.SmallInteger(), server_default='1'),
        sa.Column('shuffle_questions', sa.Boolean(), server_default='false'),
        sa.Column('shuffle_choices', sa.Boolean(), server_default='false'),
        sa.Column('show_result_after', sa.String(20), server_default='submit'),
        sa.Column('deadline', sa.DateTime(timezone=True)),
        sa.Column('is_published', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # quiz_questions
    op.create_table(
        'quiz_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('quiz_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(20), server_default='mcq'),
        sa.Column('choices', postgresql.JSONB(), nullable=False),
        sa.Column('explanation', sa.Text()),
        sa.Column('points', sa.Numeric(4, 2), server_default='1.00'),
        sa.Column('sort_order', sa.SmallInteger(), server_default='0'),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # quiz_attempts
    op.create_table(
        'quiz_attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('quiz_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('submitted_at', sa.DateTime(timezone=True)),
        sa.Column('score', sa.Numeric(5, 2)),
        sa.Column('max_score', sa.Numeric(5, 2)),
        sa.Column('attempt_no', sa.SmallInteger(), server_default='1'),
        sa.Column('late_submit', sa.Boolean(), server_default='false'),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # question_answers
    op.create_table(
        'question_answers',
        sa.Column('attempt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chosen_ids', postgresql.JSONB()),
        sa.Column('is_correct', sa.Boolean()),
        sa.ForeignKeyConstraint(['attempt_id'], ['quiz_attempts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['quiz_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('attempt_id', 'question_id'),
    )

    # user_files
    op.create_table(
        'user_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.BigInteger()),
        sa.Column('description', sa.Text()),
        sa.Column('is_public', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # file_shares
    op.create_table(
        'file_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_type', sa.String(20), server_default='user_file'),
        sa.Column('shared_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('share_token', sa.String(64), nullable=False),
        sa.Column('permission', sa.String(10), server_default='view'),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('view_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['shared_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('share_token'),
    )
    op.create_index('ix_file_shares_token', 'file_shares', ['share_token'])


def downgrade() -> None:
    tables = [
        'file_shares', 'user_files', 'question_answers', 'quiz_attempts',
        'quiz_questions', 'quizzes', 'lesson_resources', 'lessons',
        'notifications', 'submissions', 'assignment_group_members',
        'assignment_groups', 'assignments', 'class_files', 'enrollments',
        'classes', 'system_settings', 'user_roles', 'users', 'roles',
    ]
    for t in tables:
        op.drop_table(t)
