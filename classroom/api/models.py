import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Text, Numeric, SmallInteger, Integer, BigInteger,
    ForeignKey, DateTime, JSON, CheckConstraint, UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


# ─────────────────────────── helpers ────────────────────────────

def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

def now_col():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ───────────────────────────── USERS ────────────────────────────

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    user_roles: Mapped[List["UserRole"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(50), default="local")
    provider_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()

    user_roles: Mapped[List["UserRole"]] = relationship(back_populates="user", foreign_keys="[UserRole.user_id]", cascade="all, delete-orphan")
    enrollments: Mapped[List["Enrollment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    classes_taught: Mapped[List["Class"]] = relationship(back_populates="teacher", foreign_keys="Class.teacher_id")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_files: Mapped[List["UserFile"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("roles.id"), primary_key=True)
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    granted_at: Mapped[datetime] = now_col()

    user: Mapped["User"] = relationship(back_populates="user_roles", foreign_keys=[user_id])
    role: Mapped["Role"] = relationship(back_populates="user_roles")


# ─────────────────────────── CLASSES ────────────────────────────

class Class(Base):
    __tablename__ = "classes"
    id: Mapped[uuid.UUID] = uuid_pk()
    teacher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    enrollment_key: Mapped[str] = mapped_column(String(100), nullable=False)  # bcrypt hash
    max_students: Mapped[int] = mapped_column(Integer, default=200)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="chk_dates"),
    )

    teacher: Mapped["User"] = relationship(back_populates="classes_taught", foreign_keys=[teacher_id])
    enrollments: Mapped[List["Enrollment"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    files: Mapped[List["ClassFile"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    lessons: Mapped[List["Lesson"]] = relationship(back_populates="class_", cascade="all, delete-orphan")
    quizzes: Mapped[List["Quiz"]] = relationship(back_populates="class_", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"
    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    enrolled_at: Mapped[datetime] = now_col()
    status: Mapped[str] = mapped_column(String(20), default="active")

    __table_args__ = (UniqueConstraint("class_id", "user_id", name="uq_enrollment"),)

    class_: Mapped["Class"] = relationship(back_populates="enrollments")
    user: Mapped["User"] = relationship(back_populates="enrollments")


# ──────────────────────────── FILES ─────────────────────────────

class ClassFile(Base):
    __tablename__ = "class_files"
    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = now_col()

    class_: Mapped["Class"] = relationship(back_populates="files")
    uploader: Mapped[Optional["User"]] = relationship(foreign_keys=[uploaded_by])


# ─────────────────────────── ASSIGNMENTS ────────────────────────

class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    file_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("class_files.id"))
    assignment_type: Mapped[str] = mapped_column(String(20), default="homework")
    max_score: Mapped[float] = mapped_column(Numeric(5, 2), default=10.00)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    allow_resubmit: Mapped[bool] = mapped_column(Boolean, default=True)
    group_size: Mapped[int] = mapped_column(SmallInteger, default=1)
    allow_sharing: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()

    __table_args__ = (
        CheckConstraint("NOT (assignment_type = 'exam' AND allow_sharing = TRUE)", name="chk_exam_no_sharing"),
        CheckConstraint("NOT (assignment_type = 'exam' AND allow_resubmit = TRUE)", name="chk_exam_no_resubmit"),
    )

    class_: Mapped["Class"] = relationship(back_populates="assignments")
    attached_file: Mapped[Optional["ClassFile"]] = relationship(foreign_keys=[file_id])
    submissions: Mapped[List["Submission"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
    groups: Mapped[List["AssignmentGroup"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")


class AssignmentGroup(Base):
    __tablename__ = "assignment_groups"
    id: Mapped[uuid.UUID] = uuid_pk()
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    group_name: Mapped[Optional[str]] = mapped_column(String(100))
    session_path: Mapped[Optional[str]] = mapped_column(String(500))
    leader_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = now_col()

    assignment: Mapped["Assignment"] = relationship(back_populates="groups")
    leader: Mapped[Optional["User"]] = relationship(foreign_keys=[leader_id])
    members: Mapped[List["AssignmentGroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class AssignmentGroupMember(Base):
    __tablename__ = "assignment_group_members"
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignment_groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    joined_at: Mapped[datetime] = now_col()

    group: Mapped["AssignmentGroup"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


# ──────────────────────────── SUBMISSIONS ───────────────────────

class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[uuid.UUID] = uuid_pk()
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    submitted_at: Mapped[datetime] = now_col()
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    graded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    grader: Mapped[Optional["User"]] = relationship(foreign_keys=[graded_by])


# ──────────────────────────── NOTIFICATIONS ─────────────────────

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = now_col()

    user: Mapped["User"] = relationship(back_populates="notifications")


# ──────────────────────────── SYSTEM SETTINGS ───────────────────

class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at: Mapped[datetime] = now_col()


# ──────────────────────────── LESSONS ───────────────────────────

class Lesson(Base):
    __tablename__ = "lessons"
    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()

    class_: Mapped["Class"] = relationship(back_populates="lessons")
    resources: Mapped[List["LessonResource"]] = relationship(back_populates="lesson", cascade="all, delete-orphan")
    quizzes: Mapped[List["Quiz"]] = relationship(back_populates="lesson")


class LessonResource(Base):
    __tablename__ = "lesson_resources"
    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'video'|'pdf'|'link'|'data_file'
    title: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    file_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("class_files.id"))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = now_col()

    __table_args__ = (
        CheckConstraint(
            "(url IS NOT NULL AND file_id IS NULL) OR (url IS NULL AND file_id IS NOT NULL)",
            name="chk_resource_source",
        ),
    )

    lesson: Mapped["Lesson"] = relationship(back_populates="resources")
    file: Mapped[Optional["ClassFile"]] = relationship(foreign_keys=[file_id])


# ──────────────────────────── QUIZZES ───────────────────────────

class Quiz(Base):
    __tablename__ = "quizzes"
    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("lessons.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    time_limit_min: Mapped[Optional[int]] = mapped_column(SmallInteger)
    max_attempts: Mapped[Optional[int]] = mapped_column(SmallInteger, default=1)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False)
    shuffle_choices: Mapped[bool] = mapped_column(Boolean, default=False)
    show_result_after: Mapped[str] = mapped_column(String(20), default="submit")
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()

    class_: Mapped["Class"] = relationship(back_populates="quizzes")
    lesson: Mapped[Optional["Lesson"]] = relationship(back_populates="quizzes", foreign_keys=[lesson_id])
    questions: Mapped[List["QuizQuestion"]] = relationship(back_populates="quiz", cascade="all, delete-orphan")
    attempts: Mapped[List["QuizAttempt"]] = relationship(back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id: Mapped[uuid.UUID] = uuid_pk()
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), default="mcq")  # 'mcq'|'multi'|'truefalse'
    choices: Mapped[list] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    points: Mapped[float] = mapped_column(Numeric(4, 2), default=1.00)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id: Mapped[uuid.UUID] = uuid_pk()
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = now_col()
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    max_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    attempt_no: Mapped[int] = mapped_column(SmallInteger, default=1)
    late_submit: Mapped[bool] = mapped_column(Boolean, default=False)

    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    answers: Mapped[List["QuestionAnswer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class QuestionAnswer(Base):
    __tablename__ = "question_answers"
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz_questions.id", ondelete="CASCADE"), primary_key=True)
    chosen_ids: Mapped[Optional[list]] = mapped_column(JSONB)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)

    attempt: Mapped["QuizAttempt"] = relationship(back_populates="answers")
    question: Mapped["QuizQuestion"] = relationship()


# ──────────────────────────── USER FILES ────────────────────────

class UserFile(Base):
    __tablename__ = "user_files"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()

    user: Mapped["User"] = relationship(back_populates="user_files")
    shares: Mapped[List["FileShare"]] = relationship(back_populates="user_file", cascade="all, delete-orphan",
                                                     foreign_keys="FileShare.file_id",
                                                     primaryjoin="and_(FileShare.file_id == UserFile.id, FileShare.file_type == 'user_file')")


class FileShare(Base):
    __tablename__ = "file_shares"
    id: Mapped[uuid.UUID] = uuid_pk()
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), default="user_file")
    shared_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    share_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    permission: Mapped[str] = mapped_column(String(10), default="view")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = now_col()

    sharer: Mapped["User"] = relationship(foreign_keys=[shared_by])
    user_file: Mapped[Optional["UserFile"]] = relationship(
        back_populates="shares",
        foreign_keys=[file_id],
        primaryjoin="and_(FileShare.file_id == UserFile.id, FileShare.file_type == 'user_file')",
        overlaps="shares",
    )
