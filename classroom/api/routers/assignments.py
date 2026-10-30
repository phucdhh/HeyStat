"""Assignments router – CRUD + groups."""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from database import get_db
from models import (
    Class, Assignment, AssignmentGroup, AssignmentGroupMember,
    ClassFile, Enrollment, User, UserRole, Role,
)
from auth.deps import get_current_user
from services.markdown import sanitize_md

router = APIRouter(tags=["assignments"])


# ─── helpers ────────────────────────────────────────────────────

async def _get_user_roles_set(db, user_id):
    r = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return {row for (row,) in r.all()}


async def _get_class_or_404(db, class_id):
    r = await db.execute(select(Class).where(Class.id == class_id))
    cls = r.scalar_one_or_none()
    if not cls:
        raise HTTPException(404, "Lớp học không tồn tại")
    return cls


async def _get_assignment_or_404(db, assignment_id, class_id=None):
    stmt = select(Assignment).where(Assignment.id == assignment_id)
    if class_id:
        stmt = stmt.where(Assignment.class_id == class_id)
    r = await db.execute(stmt)
    a = r.scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Bài tập không tồn tại")
    return a


async def _is_enrolled(db, class_id, user_id):
    r = await db.execute(
        select(Enrollment).where(
            Enrollment.class_id == class_id,
            Enrollment.user_id == user_id,
            Enrollment.status == "active",
        )
    )
    return r.scalar_one_or_none() is not None


async def _class_access_role(db, cls, user):
    roles = await _get_user_roles_set(db, user.id)
    if "admin" in roles or cls.teacher_id == user.id:
        return "teacher"
    if await _is_enrolled(db, cls.id, user.id):
        return "student"
    raise HTTPException(403, "Không có quyền truy cập lớp học này")


async def _ensure_file_in_class(db, class_id, file_id):
    """A dataset must belong to the class it is assigned to, or one teacher could
    hand another class's files to their own students."""
    if file_id is None:
        return
    r = await db.execute(select(ClassFile).where(ClassFile.id == file_id, ClassFile.class_id == class_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(400, "Bộ dữ liệu không thuộc lớp học này")


# ─── schemas ────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str
    file_id: Optional[uuid.UUID] = None
    assignment_type: str = "homework"
    max_score: float = 10.0
    deadline: datetime
    allow_resubmit: bool = True
    group_size: int = Field(1, ge=1, le=20)
    allow_sharing: bool = False
    answer_key: Optional[dict] = None
    grading_config: Optional[dict] = None


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignment_type: Optional[str] = None
    deadline: Optional[datetime] = None
    max_score: Optional[float] = None
    allow_resubmit: Optional[bool] = None
    allow_sharing: Optional[bool] = None
    file_id: Optional[uuid.UUID] = None
    group_size: Optional[int] = Field(None, ge=1, le=20)
    answer_key: Optional[dict] = None
    grading_config: Optional[dict] = None


class AssignmentResponse(BaseModel):
    id: str
    class_id: str
    title: str
    description: str
    assignment_type: str
    max_score: float
    deadline: datetime
    allow_resubmit: bool
    group_size: int
    allow_sharing: bool
    file_id: Optional[str]
    answer_key: Optional[dict] = None
    grading_config: Optional[dict] = None
    # Question prompts a student may answer; never contains the expected answer.
    questions: Optional[list[dict]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


def _to_response(a: Assignment, *, with_key: bool) -> AssignmentResponse:
    questions = [
        {k: q[k] for k in ("id", "label", "type", "points", "comment", "comment_hint") if k in q}
        for q in (a.answer_key or {}).get("questions", [])
    ]
    return AssignmentResponse(
        id=str(a.id), class_id=str(a.class_id), title=a.title,
        description=a.description, assignment_type=a.assignment_type,
        max_score=float(a.max_score), deadline=a.deadline,
        allow_resubmit=a.allow_resubmit, group_size=a.group_size,
        allow_sharing=a.allow_sharing,
        file_id=str(a.file_id) if a.file_id else None,
        answer_key=a.answer_key if with_key else None,
        grading_config=a.grading_config if with_key else None,
        questions=questions or None,
        created_at=a.created_at,
    )


class GroupCreate(BaseModel):
    group_name: Optional[str] = None


class GroupJoin(BaseModel):
    group_id: uuid.UUID


class GroupMemberInfo(BaseModel):
    user_id: str
    full_name: Optional[str] = None


class GroupResponse(BaseModel):
    id: str
    assignment_id: str
    group_name: Optional[str]
    leader_id: Optional[str]
    member_count: int = 0
    members: list[GroupMemberInfo] = []

    model_config = {"from_attributes": True}


# ─── assignment CRUD ─────────────────────────────────────────────

@router.get("/classes/{class_id}/assignments", response_model=list[AssignmentResponse])
async def list_assignments(
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    access = await _class_access_role(db, cls, current_user)
    r = await db.execute(select(Assignment).where(Assignment.class_id == class_id))
    assignments = r.scalars().all()
    return [_to_response(a, with_key=access == "teacher") for a in assignments]


@router.post("/classes/{class_id}/assignments", status_code=201, response_model=AssignmentResponse)
async def create_assignment(
    class_id: uuid.UUID,
    body: AssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Chỉ giáo viên mới tạo được bài tập")
    if body.assignment_type not in ("homework", "project", "exam"):
        raise HTTPException(400, "Loại bài tập không hợp lệ")
    if body.assignment_type == "exam":
        body.allow_sharing = False
        body.allow_resubmit = False
    await _ensure_file_in_class(db, class_id, body.file_id)
    a = Assignment(
        class_id=class_id,
        title=body.title,
        description=sanitize_md(body.description),
        file_id=body.file_id,
        assignment_type=body.assignment_type,
        max_score=body.max_score,
        deadline=body.deadline,
        allow_resubmit=body.allow_resubmit,
        group_size=body.group_size,
        allow_sharing=body.allow_sharing,
        answer_key=body.answer_key,
        grading_config=body.grading_config,
    )
    db.add(a)
    await db.flush()
    return _to_response(a, with_key=True)


@router.get("/classes/{class_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    class_id: uuid.UUID, assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    access = await _class_access_role(db, cls, current_user)
    a = await _get_assignment_or_404(db, assignment_id, class_id)
    return _to_response(a, with_key=access == "teacher")


@router.patch("/classes/{class_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    class_id: uuid.UUID, assignment_id: uuid.UUID,
    body: AssignmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Không có quyền cập nhật bài tập")
    a = await _get_assignment_or_404(db, assignment_id, class_id)
    # exclude_unset keeps an explicit null, so clearing the grading config works
    updates = body.model_dump(exclude_unset=True)
    if "description" in updates:
        updates["description"] = sanitize_md(updates["description"])
    if "file_id" in updates:
        await _ensure_file_in_class(db, class_id, updates["file_id"])
    # chk_exam_no_sharing / chk_exam_no_resubmit reject the row otherwise, same as on create
    if updates.get("assignment_type") == "exam":
        updates["allow_sharing"] = False
        updates["allow_resubmit"] = False
    # the marks students saw must follow the rules they were graded against
    criteria_changed = any(
        field in updates and updates[field] != getattr(a, field)
        for field in ("grading_config", "answer_key", "max_score")
    )
    for field, val in updates.items():
        setattr(a, field, val)
    a.updated_at = datetime.now(tz=timezone.utc)
    if criteria_changed:
        from routers.submissions import regrade_assignment
        await regrade_assignment(db, a)
    return _to_response(a, with_key=True)


@router.delete("/classes/{class_id}/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    class_id: uuid.UUID, assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Không có quyền xoá bài tập")
    a = await _get_assignment_or_404(db, assignment_id, class_id)
    await db.delete(a)


# ─── assignment dataset (cloned per student) ─────────────────────

@router.get("/assignments/{assignment_id}/dataset")
async def get_assignment_dataset(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream the assignment's data file under a per-student clone name.

    The browser hands this to jamovi's /open, so every student works on
    ``Dataset_[Student]_[Assignment].<ext>`` and never on the teacher's original.
    """
    a = await _get_assignment_or_404(db, assignment_id)
    if not await _is_enrolled(db, a.class_id, current_user.id):
        roles = await _get_user_roles_set(db, current_user.id)
        cls_r = await db.execute(select(Class).where(Class.id == a.class_id))
        cls = cls_r.scalar_one()
        if "admin" not in roles and cls.teacher_id != current_user.id:
            raise HTTPException(403, "Bạn chưa tham gia lớp học này")
    if not a.file_id:
        raise HTTPException(404, "Bài tập không kèm bộ dữ liệu")

    fr = await db.execute(select(ClassFile).where(ClassFile.id == a.file_id))
    cf = fr.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "Bộ dữ liệu không tồn tại")

    from config import get_settings
    from fastapi.responses import FileResponse

    full_path = Path(get_settings().upload_dir) / cf.file_path
    if not full_path.exists():
        raise HTTPException(404, "Bộ dữ liệu không tồn tại trên server")

    ext = Path(cf.file_name).suffix or ".omv"
    clone_name = f"Dataset_{str(current_user.id)[:8]}_{str(assignment_id)[:8]}{ext}"
    return FileResponse(
        path=str(full_path),
        filename=clone_name,
        media_type="application/octet-stream",
    )


@router.get("/assignments/{assignment_id}/grading-schema")
async def get_grading_schema(
    assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """What the teacher's own ``.omv`` already contains, for building checks.

    Returns ``[{name, module, tables: [{title, columns, row_labels}]}]`` so the
    grading config can be filled from pickers instead of guessed strings.
    """
    a = await _get_assignment_or_404(db, assignment_id)
    cls_r = await db.execute(select(Class).where(Class.id == a.class_id))
    cls = cls_r.scalar_one()
    roles = await _get_user_roles_set(db, current_user.id)
    if "admin" not in roles and cls.teacher_id != current_user.id:
        raise HTTPException(403, "Chỉ giáo viên mới xem được cấu hình chấm")
    if not a.file_id:
        return {"file_name": None, "analyses": []}

    fr = await db.execute(select(ClassFile).where(ClassFile.id == a.file_id))
    cf = fr.scalar_one_or_none()
    if not cf:
        raise HTTPException(404, "Bộ dữ liệu không tồn tại")

    from config import get_settings
    from services.omv_reader import grading_schema, parse_omv

    full_path = Path(get_settings().upload_dir) / cf.file_path
    if not full_path.exists():
        raise HTTPException(404, "Bộ dữ liệu không tồn tại trên server")
    try:
        doc = parse_omv(full_path.read_bytes())
    except Exception as exc:
        raise HTTPException(422, f"Không đọc được bảng kết quả từ file này: {exc}")

    return {"file_name": cf.file_name, "analyses": grading_schema(doc)}


# ─── groups ─────────────────────────────────────────────────────

@router.get("/classes/{class_id}/assignments/{assignment_id}/groups", response_model=list[GroupResponse])
async def list_groups(
    class_id: uuid.UUID, assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _class_access_role(db, cls, current_user)
    a = await _get_assignment_or_404(db, assignment_id, class_id)
    r = await db.execute(select(AssignmentGroup).where(AssignmentGroup.assignment_id == assignment_id))
    groups = r.scalars().all()
    result = []
    for g in groups:
        mc = await db.execute(
            select(AssignmentGroupMember, User)
            .join(User, User.id == AssignmentGroupMember.user_id)
            .where(AssignmentGroupMember.group_id == g.id)
        )
        rows = mc.all()
        members = [GroupMemberInfo(user_id=str(m.user_id), full_name=u.full_name) for m, u in rows]
        result.append(GroupResponse(
            id=str(g.id), assignment_id=str(g.assignment_id),
            group_name=g.group_name,
            leader_id=str(g.leader_id) if g.leader_id else None,
            member_count=len(rows),
            members=members,
        ))
    return result


@router.post("/classes/{class_id}/assignments/{assignment_id}/groups", status_code=201)
async def create_or_join_group(
    class_id: uuid.UUID, assignment_id: uuid.UUID,
    body: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    access = await _class_access_role(db, cls, current_user)
    if access != "student":
        raise HTTPException(403, "Chỉ sinh viên mới tạo nhóm được")
    a = await _get_assignment_or_404(db, assignment_id, class_id)
    if a.assignment_type == "exam":
        raise HTTPException(403, "Bài kiểm tra không hỗ trợ nhóm")
    if a.group_size <= 1:
        raise HTTPException(400, "Bài tập cá nhân không cần tạo nhóm")

    # Check student not already in a group for this assignment
    existing_member = await db.execute(
        select(AssignmentGroupMember)
        .join(AssignmentGroup, AssignmentGroup.id == AssignmentGroupMember.group_id)
        .where(
            AssignmentGroup.assignment_id == assignment_id,
            AssignmentGroupMember.user_id == current_user.id,
        )
    )
    if existing_member.scalar_one_or_none():
        raise HTTPException(400, "Bạn đã tham gia nhóm rồi")

    import os
    session_path = f"classroom/{class_id}/group_{uuid.uuid4()}"
    group = AssignmentGroup(
        assignment_id=assignment_id,
        group_name=body.group_name or f"Nhóm mới",
        session_path=session_path,
        leader_id=current_user.id,
    )
    db.add(group)
    await db.flush()
    db.add(AssignmentGroupMember(group_id=group.id, user_id=current_user.id))
    return {"id": str(group.id), "group_name": group.group_name, "session_path": session_path}


@router.post("/classes/{class_id}/assignments/{assignment_id}/groups/join", status_code=200)
async def join_group(
    class_id: uuid.UUID, assignment_id: uuid.UUID,
    body: GroupJoin,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    access = await _class_access_role(db, cls, current_user)
    if access != "student":
        raise HTTPException(403, "Chỉ sinh viên mới tham gia nhóm được")
    a = await _get_assignment_or_404(db, assignment_id, class_id)
    if a.assignment_type == "exam":
        raise HTTPException(403, "Bài kiểm tra không hỗ trợ nhóm")

    # Check not already in a group
    existing = await db.execute(
        select(AssignmentGroupMember)
        .join(AssignmentGroup, AssignmentGroup.id == AssignmentGroupMember.group_id)
        .where(
            AssignmentGroup.assignment_id == assignment_id,
            AssignmentGroupMember.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Bạn đã tham gia nhóm rồi")

    # Check group exists and has space
    r = await db.execute(
        select(AssignmentGroup).where(
            AssignmentGroup.id == body.group_id,
            AssignmentGroup.assignment_id == assignment_id,
        )
    )
    group = r.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Nhóm không tồn tại")
    mc = await db.execute(
        select(AssignmentGroupMember).where(AssignmentGroupMember.group_id == group.id)
    )
    if len(mc.scalars().all()) >= a.group_size:
        raise HTTPException(400, "Nhóm đã đầy")

    db.add(AssignmentGroupMember(group_id=group.id, user_id=current_user.id))
    return {"detail": "Tham gia nhóm thành công"}


@router.patch("/classes/{class_id}/assignments/{assignment_id}/groups/{group_id}/leader", status_code=200)
async def transfer_leader(
    class_id: uuid.UUID, assignment_id: uuid.UUID, group_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(AssignmentGroup).where(
            AssignmentGroup.id == group_id,
            AssignmentGroup.assignment_id == assignment_id,
        )
    )
    group = r.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Nhóm không tồn tại")
    if group.leader_id != current_user.id:
        raise HTTPException(403, "Chỉ leader mới chuyển quyền được")
    new_leader_id_str = body.get("new_leader_id")
    if not new_leader_id_str:
        raise HTTPException(422, "new_leader_id là bắt buộc")
    try:
        new_leader_id = uuid.UUID(str(new_leader_id_str))
    except ValueError:
        raise HTTPException(422, "new_leader_id không hợp lệ")
    # Verify new leader is in group
    member_check = await db.execute(
        select(AssignmentGroupMember).where(
            AssignmentGroupMember.group_id == group_id,
            AssignmentGroupMember.user_id == new_leader_id,
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(400, "Người dùng không phải thành viên nhóm")
    group.leader_id = new_leader_id
    return {"detail": "Chuyển quyền leader thành công"}
