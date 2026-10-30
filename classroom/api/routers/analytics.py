"""Analytics router – student skill mastery and class-wide misconception report."""
import unicodedata
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import (
    Assignment, Class, Enrollment, Submission, User, UserRole, Role,
)
from auth.deps import get_current_user

router = APIRouter(tags=["analytics"])


async def _get_user_roles(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


# jamovi module id -> the skill name shown to students
SKILLS = {
    "descriptives": "Mô tả (Descriptives)",
    "freqs": "Tần số (Frequencies)",
    "ttestIS": "t-test hai mẫu độc lập",
    "TtestOneSamp": "t-test một mẫu",
    "pairedSamplesTTest": "t-test mẫu phụ thuộc",
    "ANOVA": "ANOVA một chiều",
    "anovaOneW": "ANOVA một chiều (Welch)",
    "anovaNP": "Kruskal-Wallis (ANOVA phi tham số)",
    "linReg": "Hồi quy tuyến tính",
    "logReg": "Hồi quy logistic",
    "corr": "Tương quan Pearson",
    "corrPart": "Tương quan từng phần",
    "jammGLM": "GLM / Trung gian (Mediation)",
    "proptest": "Kiểm định tỉ lệ",
    "contTables": "Bảng ngẫu nhiên (Chi-bình phương)",
}


# older snapshots have no module list, so fall back to the rendered analysis title
_SKILL_ALIASES = {
    "descriptives": "descriptive",
    "freqs": "frequenc",
    "ttestIS": "independent samples t-test",
    "TtestOneSamp": "one sample t-test",
    "pairedSamplesTTest": "paired",
    "ANOVA": "one-way anova",
    "anovaOneW": "welch",
    "anovaNP": "kruskal",
    "linReg": "linear regression",
    "logReg": "logistic regression",
    "corr": "correlation",
    "corrPart": "partial correlation",
    "jammGLM": "mediation",
    "proptest": "proportion",
    "contTables": "contingency",
}


def _modules_of(sub: Submission) -> list[str]:
    snapshot = sub.session_snapshot or {}
    recorded = [m for m in (snapshot.get("modules") or []) if m in SKILLS]
    if recorded:
        return recorded
    # a report titled in Vietnamese still spells these analyses in English
    text = "".join(c for c in unicodedata.normalize("NFD", " ".join(
        (t.get("analysis") or "") + " " + (t.get("title") or "")
        for t in (snapshot.get("tables") or snapshot.get("available") or [])
    ).lower()) if unicodedata.category(c) != "Mn")
    found = []
    for module_id, alias in _SKILL_ALIASES.items():
        if module_id in text or alias in text:
            found.append(module_id)
    return found


def _mastery_rows(subs: list[Submission]) -> list[dict]:
    """Per-skill practice counts; a skill counts as mastered when the whole
    submission that used it had no failed criterion."""
    stats: dict[str, dict] = {}
    for sub in subs:
        grade = sub.auto_grade or {}
        mistakes = int(grade.get("mistake_count", 0))
        for module_id in _modules_of(sub):
            row = stats.setdefault(module_id, {"skill": module_id, "label": SKILLS[module_id],
                                               "attempts": 0, "mastered": 0})
            row["attempts"] += 1
            if mistakes == 0 and grade:
                row["mastered"] += 1
    rows = sorted(stats.values(), key=lambda r: r["label"])
    for r in rows:
        r["accuracy"] = round(r["mastered"] / r["attempts"], 2) if r["attempts"] else 0.0
    return rows


@router.get("/analytics/my")
async def my_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Student dashboard: assignment progress plus statistics skills mastered."""
    subs_r = await db.execute(
        select(Submission, Assignment)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .where(Submission.student_id == current_user.id, Submission.is_final == True)
    )
    rows = subs_r.all()

    assignments_r = await db.execute(
        select(Assignment)
        .join(Enrollment, Enrollment.class_id == Assignment.class_id)
        .where(Enrollment.user_id == current_user.id, Enrollment.status == "active")
    )
    total_assignments = len(assignments_r.scalars().all())

    # Students see when they handed in, never the mark; the teacher publishes
    # điểm outside the app.
    recent = [
        {
            "assignment_id": str(a.id),
            "title": a.title,
            "class_id": str(a.class_id),
            "submitted_at": s.submitted_at,
        }
        for s, a in sorted(rows, key=lambda r: r[0].submitted_at, reverse=True)[:10]
    ]

    return {
        "assignments_completed": len(rows),
        "assignments_total": total_assignments,
        "skills": _mastery_rows([s for s, _ in rows]),
        "recent": recent,
    }


@router.get("/classes/{class_id}/analytics")
async def class_analytics(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Teacher dashboard: engagement, then the criteria students miss most."""
    cls_r = await db.execute(select(Class).where(Class.id == class_id))
    cls = cls_r.scalar_one_or_none()
    if not cls:
        raise HTTPException(404, "Lớp học không tồn tại")
    roles = await _get_user_roles(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Không có quyền xem phân tích")

    students_r = await db.execute(
        select(User).join(Enrollment, Enrollment.user_id == User.id)
        .where(Enrollment.class_id == class_id, Enrollment.status == "active")
    )
    students = students_r.scalars().all()
    student_ids = {s.id for s in students}

    assignments_r = await db.execute(select(Assignment).where(Assignment.class_id == class_id))
    assignments = assignments_r.scalars().all()
    assignment_ids = {a.id for a in assignments}

    subs_r = await db.execute(
        select(Submission).where(Submission.assignment_id.in_(assignment_ids or {uuid.uuid4()}))
    )
    submissions = [s for s in subs_r.scalars().all() if s.student_id in student_ids]
    finals = [s for s in submissions if s.is_final]

    drafts = len([s for s in submissions if not s.is_final])
    scores = [float(s.score) for s in finals if s.score is not None]
    active_students = {s.student_id for s in finals}

    # misconceptions: every failed criterion label across the class
    missed: Counter = Counter()
    skill_attempts: Counter = Counter()
    skill_clean: Counter = Counter()
    for s in finals:
        grade = s.auto_grade or {}
        for item in grade.get("items", []):
            if not item.get("passed"):
                key = item.get("label") or item.get("id") or "Không rõ"
                missed[(key, item.get("explanation") or "")] += 1
        for module_id in _modules_of(s):
            skill_attempts[module_id] += 1
            if grade and grade.get("mistake_count") == 0:
                skill_clean[module_id] += 1

    return {
        "engagement": {
            "students": len(students),
            "students_submitted": len(active_students),
            "submitted_rate": round(len(active_students) / len(students), 2) if students else None,
            "assignments": len(assignments),
            "final_submissions": len(finals),
            "draft_snapshots": drafts,
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        },
        "misconceptions": [
            {"label": label, "explanation": explanation, "count": count}
            for (label, explanation), count in missed.most_common(10)
        ],
        "skills": [
            {
                "skill": module_id,
                "label": SKILLS[module_id],
                "attempts": attempts,
                "accuracy": round(skill_clean[module_id] / attempts, 2) if attempts else 0.0,
            }
            for module_id, attempts in skill_attempts.most_common()
        ],
    }
