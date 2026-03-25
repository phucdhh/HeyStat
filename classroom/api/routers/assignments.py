"""Assignments router – CRUD + groups."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from database import get_db
from models import (
    Class, Assignment, AssignmentGroup, AssignmentGroupMember,
    Enrollment, User, UserRole, Role,
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


# ─── schemas ────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str
    file_id: Optional[uuid.UUID] = None
    assignment_type: str = "homework"
    max_score: float = 10.0
    deadline: datetime
    allow_resubmit: bool = True
    group_size: int = 1
    allow_sharing: bool = False


class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    max_score: Optional[float] = None
    allow_resubmit: Optional[bool] = None
    allow_sharing: Optional[bool] = None


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
    created_at: datetime

    model_config = {"from_attributes": True}


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
    await _class_access_role(db, cls, current_user)
    r = await db.execute(select(Assignment).where(Assignment.class_id == class_id))
    assignments = r.scalars().all()
    return [
        AssignmentResponse(
            id=str(a.id), class_id=str(a.class_id), title=a.title,
            description=a.description, assignment_type=a.assignment_type,
            max_score=float(a.max_score), deadline=a.deadline,
            allow_resubmit=a.allow_resubmit, group_size=a.group_size,
            allow_sharing=a.allow_sharing,
            file_id=str(a.file_id) if a.file_id else None,
            created_at=a.created_at,
        )
        for a in assignments
    ]


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
    if body.assignment_type == "exam":
        body.allow_sharing = False
        body.allow_resubmit = False
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
    )
    db.add(a)
    await db.flush()
    return AssignmentResponse(
        id=str(a.id), class_id=str(a.class_id), title=a.title,
        description=a.description, assignment_type=a.assignment_type,
        max_score=float(a.max_score), deadline=a.deadline,
        allow_resubmit=a.allow_resubmit, group_size=a.group_size,
        allow_sharing=a.allow_sharing,
        file_id=str(a.file_id) if a.file_id else None,
        created_at=a.created_at,
    )


@router.get("/classes/{class_id}/assignments/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    class_id: uuid.UUID, assignment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cls = await _get_class_or_404(db, class_id)
    await _class_access_role(db, cls, current_user)
    a = await _get_assignment_or_404(db, assignment_id, class_id)
    return AssignmentResponse(
        id=str(a.id), class_id=str(a.class_id), title=a.title,
        description=a.description, assignment_type=a.assignment_type,
        max_score=float(a.max_score), deadline=a.deadline,
        allow_resubmit=a.allow_resubmit, group_size=a.group_size,
        allow_sharing=a.allow_sharing,
        file_id=str(a.file_id) if a.file_id else None,
        created_at=a.created_at,
    )


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
    updates = body.model_dump(exclude_none=True)
    if "description" in updates:
        updates["description"] = sanitize_md(updates["description"])
    for field, val in updates.items():
        setattr(a, field, val)
    a.updated_at = datetime.now(tz=timezone.utc)
    return AssignmentResponse(
        id=str(a.id), class_id=str(a.class_id), title=a.title,
        description=a.description, assignment_type=a.assignment_type,
        max_score=float(a.max_score), deadline=a.deadline,
        allow_resubmit=a.allow_resubmit, group_size=a.group_size,
        allow_sharing=a.allow_sharing,
        file_id=str(a.file_id) if a.file_id else None,
        created_at=a.created_at,
    )


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
