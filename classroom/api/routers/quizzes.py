"""Quizzes router – CRUD, questions, attempts, auto-grade (Phase 12)."""
import uuid
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from database import get_db
from models import (
    Class, Quiz, QuizQuestion, QuizAttempt, QuestionAnswer,
    Enrollment, User, UserRole, Role,
)
from auth.deps import get_current_user
from services.markdown import sanitize_md
from services.quiz_grader import calculate_score

router = APIRouter(tags=["quizzes"])


async def _get_user_roles(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def _class_access(db, class_id, user):
    r = await db.execute(select(Class).where(Class.id == class_id))
    cls = r.scalar_one_or_none()
    if not cls:
        raise HTTPException(404)
    roles = await _get_user_roles(db, user.id)
    if "admin" in roles or cls.teacher_id == user.id:
        return cls, "teacher"
    er = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == class_id, Enrollment.user_id == user.id, Enrollment.status == "active"
        )
    )
    if er.scalar_one_or_none():
        return cls, "student"
    raise HTTPException(403)


# ─── schemas ────────────────────────────────────────────────────

class QuizCreate(BaseModel):
    title: str
    description: Optional[str] = None
    lesson_id: Optional[uuid.UUID] = None
    time_limit_min: Optional[int] = None
    max_attempts: Optional[int] = 1
    shuffle_questions: bool = False
    shuffle_choices: bool = False
    show_result_after: str = "submit"
    deadline: Optional[datetime] = None


class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    time_limit_min: Optional[int] = None
    max_attempts: Optional[int] = None
    shuffle_questions: Optional[bool] = None
    shuffle_choices: Optional[bool] = None
    show_result_after: Optional[str] = None
    deadline: Optional[datetime] = None
    is_published: Optional[bool] = None


class QuizResponse(BaseModel):
    id: str
    class_id: str
    lesson_id: Optional[str]
    title: str
    description: Optional[str]
    time_limit_min: Optional[int]
    max_attempts: Optional[int]
    shuffle_questions: bool
    shuffle_choices: bool
    show_result_after: str
    deadline: Optional[datetime]
    is_published: bool
    question_count: int = 0

    model_config = {"from_attributes": True}


class QuestionCreate(BaseModel):
    question_text: str
    question_type: str = "mcq"  # 'mcq' | 'multi' | 'truefalse'
    choices: list[dict]  # [{"id": "a", "text": "...", "is_correct": true}, ...]
    explanation: Optional[str] = None
    points: float = 1.0
    sort_order: int = 0


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    choices: Optional[list[dict]] = None
    explanation: Optional[str] = None
    points: Optional[float] = None
    sort_order: Optional[int] = None


class ChoicePublic(BaseModel):
    id: str
    text: str


class QuestionPublic(BaseModel):
    """Returned to students – no is_correct or explanation before submission."""
    id: str
    question_text: str
    question_type: str
    choices: list[ChoicePublic]
    points: float
    sort_order: int


class AnswerInput(BaseModel):
    question_id: uuid.UUID
    chosen_ids: list[str]


class SubmitAttemptRequest(BaseModel):
    answers: list[AnswerInput]


class ReorderRequest(BaseModel):
    order: list[str]


# ─── Quiz CRUD ───────────────────────────────────────────────────

@router.get("/classes/{class_id}/quizzes", response_model=list[QuizResponse])
async def list_quizzes(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    stmt = select(Quiz).where(Quiz.class_id == class_id)
    if role == "student":
        stmt = stmt.where(Quiz.is_published == True)
    r = await db.execute(stmt)
    quizzes = r.scalars().all()
    result = []
    for q in quizzes:
        cnt = (await db.execute(select(func.count(QuizQuestion.id)).where(QuizQuestion.quiz_id == q.id))).scalar()
        result.append(QuizResponse(
            id=str(q.id), class_id=str(q.class_id),
            lesson_id=str(q.lesson_id) if q.lesson_id else None,
            title=q.title, description=q.description,
            time_limit_min=q.time_limit_min, max_attempts=q.max_attempts,
            shuffle_questions=q.shuffle_questions, shuffle_choices=q.shuffle_choices,
            show_result_after=q.show_result_after, deadline=q.deadline,
            is_published=q.is_published, question_count=cnt or 0,
        ))
    return result


@router.post("/classes/{class_id}/quizzes", status_code=201, response_model=QuizResponse)
async def create_quiz(
    class_id: uuid.UUID, body: QuizCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    quiz = Quiz(
        class_id=class_id,
        lesson_id=body.lesson_id,
        title=body.title,
        description=body.description,
        time_limit_min=body.time_limit_min,
        max_attempts=body.max_attempts,
        shuffle_questions=body.shuffle_questions,
        shuffle_choices=body.shuffle_choices,
        show_result_after=body.show_result_after,
        deadline=body.deadline,
    )
    db.add(quiz)
    await db.flush()
    return QuizResponse(
        id=str(quiz.id), class_id=str(quiz.class_id),
        lesson_id=str(quiz.lesson_id) if quiz.lesson_id else None,
        title=quiz.title, description=quiz.description,
        time_limit_min=quiz.time_limit_min, max_attempts=quiz.max_attempts,
        shuffle_questions=quiz.shuffle_questions, shuffle_choices=quiz.shuffle_choices,
        show_result_after=quiz.show_result_after, deadline=quiz.deadline,
        is_published=quiz.is_published, question_count=0,
    )


@router.patch("/classes/{class_id}/quizzes/{quiz_id}", response_model=QuizResponse)
async def update_quiz(
    class_id: uuid.UUID, quiz_id: uuid.UUID, body: QuizUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    r = await db.execute(select(Quiz).where(Quiz.id == quiz_id, Quiz.class_id == class_id))
    quiz = r.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(quiz, field, val)
    quiz.updated_at = datetime.now(tz=timezone.utc)
    cnt = (await db.execute(select(func.count(QuizQuestion.id)).where(QuizQuestion.quiz_id == quiz.id))).scalar()
    return QuizResponse(
        id=str(quiz.id), class_id=str(quiz.class_id),
        lesson_id=str(quiz.lesson_id) if quiz.lesson_id else None,
        title=quiz.title, description=quiz.description,
        time_limit_min=quiz.time_limit_min, max_attempts=quiz.max_attempts,
        shuffle_questions=quiz.shuffle_questions, shuffle_choices=quiz.shuffle_choices,
        show_result_after=quiz.show_result_after, deadline=quiz.deadline,
        is_published=quiz.is_published, question_count=cnt or 0,
    )


@router.delete("/classes/{class_id}/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(
    class_id: uuid.UUID, quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    r = await db.execute(select(Quiz).where(Quiz.id == quiz_id, Quiz.class_id == class_id))
    quiz = r.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404)
    await db.delete(quiz)


# ─── Questions ──────────────────────────────────────────────────

@router.post("/classes/{class_id}/quizzes/{quiz_id}/questions", status_code=201)
async def add_question(
    class_id: uuid.UUID, quiz_id: uuid.UUID, body: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls, role = await _class_access(db, class_id, current_user)
    if role != "teacher":
        raise HTTPException(403)
    q = QuizQuestion(
        quiz_id=quiz_id,
        question_text=sanitize_md(body.question_text),
        question_type=body.question_type,
        choices=body.choices,
        explanation=sanitize_md(body.explanation),
        points=body.points,
        sort_order=body.sort_order,
    )
    db.add(q)
    await db.flush()
    return {"id": str(q.id), "question_text": q.question_text, "question_type": q.question_type}


@router.patch("/quizzes/{quiz_id}/questions/{question_id}")
async def update_question(
    quiz_id: uuid.UUID, question_id: uuid.UUID, body: QuestionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(QuizQuestion).where(QuizQuestion.id == question_id, QuizQuestion.quiz_id == quiz_id)
    )
    q = r.scalar_one_or_none()
    if not q:
        raise HTTPException(404)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(q, field, val)
    return {"id": str(q.id), "question_text": q.question_text}


@router.delete("/quizzes/{quiz_id}/questions/{question_id}", status_code=204)
async def delete_question(
    quiz_id: uuid.UUID, question_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(QuizQuestion).where(QuizQuestion.id == question_id, QuizQuestion.quiz_id == quiz_id)
    )
    q = r.scalar_one_or_none()
    if not q:
        raise HTTPException(404)
    await db.delete(q)


@router.patch("/quizzes/{quiz_id}/questions/reorder", status_code=204)
async def reorder_questions(
    quiz_id: uuid.UUID, body: ReorderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for idx, qid in enumerate(body.order):
        r = await db.execute(
            select(QuizQuestion).where(QuizQuestion.id == uuid.UUID(qid), QuizQuestion.quiz_id == quiz_id)
        )
        q = r.scalar_one_or_none()
        if q:
            q.sort_order = idx


# ─── Attempts ───────────────────────────────────────────────────

@router.post("/quizzes/{quiz_id}/attempts", status_code=201)
async def start_attempt(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = r.scalar_one_or_none()
    if not quiz or not quiz.is_published:
        raise HTTPException(404, "Quiz không tồn tại hoặc chưa được xuất bản")

    # Check enrollment
    er = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == quiz.class_id,
            Enrollment.user_id == current_user.id,
            Enrollment.status == "active",
        )
    )
    if not er.scalar_one_or_none():
        raise HTTPException(403, "Bạn chưa tham gia lớp học")

    # Check deadline
    now = datetime.now(tz=timezone.utc)
    if quiz.deadline and now > quiz.deadline.replace(tzinfo=timezone.utc):
        raise HTTPException(403, "Quiz đã hết hạn")

    # Check attempt count
    if quiz.max_attempts:
        cnt = (await db.execute(
            select(func.count(QuizAttempt.id)).where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.student_id == current_user.id,
                QuizAttempt.submitted_at.isnot(None),
            )
        )).scalar()
        if cnt >= quiz.max_attempts:
            raise HTTPException(400, f"Bạn đã làm hết {quiz.max_attempts} lượt")

    # Get attempt_no
    attempt_no_r = await db.execute(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.student_id == current_user.id,
        )
    )
    attempt_no = (attempt_no_r.scalar() or 0) + 1

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        student_id=current_user.id,
        attempt_no=attempt_no,
    )
    db.add(attempt)
    await db.flush()

    # Load questions for student (without is_correct)
    q_r = await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.sort_order)
    )
    questions = q_r.scalars().all()
    if quiz.shuffle_questions:
        questions = list(questions)
        random.shuffle(questions)

    def strip_correct(choices, shuffle):
        result = [{"id": c["id"], "text": c["text"]} for c in choices]
        if shuffle:
            random.shuffle(result)
        return result

    return {
        "attempt_id": str(attempt.id),
        "attempt_no": attempt_no,
        "started_at": attempt.started_at.isoformat(),
        "time_limit_min": quiz.time_limit_min,
        "questions": [
            {
                "id": str(q.id),
                "question_text": q.question_text,
                "question_type": q.question_type,
                "choices": strip_correct(q.choices, quiz.shuffle_choices),
                "points": float(q.points),
            }
            for q in questions
        ],
    }


@router.patch("/quizzes/{quiz_id}/attempts/{attempt_id}/submit")
async def submit_attempt(
    quiz_id: uuid.UUID, attempt_id: uuid.UUID,
    body: SubmitAttemptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.id == attempt_id,
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.student_id == current_user.id,
        )
    )
    attempt = r.scalar_one_or_none()
    if not attempt:
        raise HTTPException(404)
    if attempt.submitted_at:
        raise HTTPException(400, "Bạn đã nộp bài quiz này rồi")

    quiz_r = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz_r.scalar_one()

    now = datetime.now(tz=timezone.utc)
    late = False
    if quiz.time_limit_min:
        deadline_time = attempt.started_at.replace(tzinfo=timezone.utc) + timedelta(minutes=quiz.time_limit_min)
        if now > deadline_time:
            late = True

    # Load all questions (teacher view – with is_correct)
    q_r = await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
    )
    questions = q_r.scalars().all()

    q_dicts = [
        {
            "id": str(q.id),
            "question_type": q.question_type,
            "choices": q.choices,
            "points": float(q.points),
        }
        for q in questions
    ]
    answers_in = [{"question_id": str(a.question_id), "chosen_ids": a.chosen_ids} for a in body.answers]
    earned, max_score, graded = calculate_score(q_dicts, answers_in)

    attempt.submitted_at = now
    attempt.score = earned
    attempt.max_score = max_score
    attempt.late_submit = late

    # Save per-question answers
    for ga in graded:
        db.add(QuestionAnswer(
            attempt_id=attempt_id,
            question_id=uuid.UUID(ga["question_id"]),
            chosen_ids=ga["chosen_ids"],
            is_correct=ga["is_correct"],
        ))

    # Build response based on show_result_after
    response: dict = {
        "attempt_id": str(attempt_id),
        "score": earned,
        "max_score": max_score,
        "late_submit": late,
    }
    if quiz.show_result_after == "submit":
        # Include per-question results + explanations
        q_explain_map = {str(q.id): q.explanation for q in questions}
        response["answers"] = [
            {
                **ga,
                "explanation": q_explain_map.get(ga["question_id"]) if ga["is_correct"] is not None else None,
            }
            for ga in graded
        ]
    return response


@router.get("/quizzes/{quiz_id}/attempts/my")
async def my_attempts(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.student_id == current_user.id,
        ).order_by(QuizAttempt.started_at.desc())
    )
    attempts = r.scalars().all()
    return [
        {
            "id": str(a.id),
            "attempt_no": a.attempt_no,
            "started_at": a.started_at.isoformat(),
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            "score": float(a.score) if a.score is not None else None,
            "max_score": float(a.max_score) if a.max_score is not None else None,
        }
        for a in attempts
    ]


@router.get("/quizzes/{quiz_id}/attempts")
async def all_attempts(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quiz_r = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz_r.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404)
    roles = await _get_user_roles(db, current_user.id)
    cls_r = await db.execute(select(Class).where(Class.id == quiz.class_id))
    cls = cls_r.scalar_one()
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403)
    r = await db.execute(
        select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.submitted_at.isnot(None))
    )
    return [{"id": str(a.id), "student_id": str(a.student_id), "score": float(a.score) if a.score else None,
             "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None} for a in r.scalars().all()]


@router.get("/quizzes/{quiz_id}/stats")
async def quiz_stats(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quiz_r = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = quiz_r.scalar_one_or_none()
    if not quiz:
        raise HTTPException(404)
    roles = await _get_user_roles(db, current_user.id)
    cls_r = await db.execute(select(Class).where(Class.id == quiz.class_id))
    cls = cls_r.scalar_one()
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403)

    total_attempts_r = await db.execute(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.quiz_id == quiz_id, QuizAttempt.submitted_at.isnot(None)
        )
    )
    total = total_attempts_r.scalar() or 0

    q_r = await db.execute(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id))
    questions = q_r.scalars().all()

    per_question = []
    for q in questions:
        # Count choices
        ans_r = await db.execute(
            select(QuestionAnswer)
            .join(QuizAttempt, QuizAttempt.id == QuestionAnswer.attempt_id)
            .where(QuestionAnswer.question_id == q.id, QuizAttempt.submitted_at.isnot(None))
        )
        all_answers = ans_r.scalars().all()
        choice_counts: dict[str, int] = {}
        for ans in all_answers:
            for cid in (ans.chosen_ids or []):
                choice_counts[cid] = choice_counts.get(cid, 0) + 1

        choices_stats = [
            {
                "choice_id": c["id"],
                "text": c["text"],
                "selected_pct": round(choice_counts.get(c["id"], 0) / max(total, 1), 3),
                "is_correct": c.get("is_correct", False),
            }
            for c in q.choices
        ]
        per_question.append({"question_id": str(q.id), "choices": choices_stats})

    return {"total_attempts": total, "per_question": per_question}
