"""Родительский доступ: прогресс, посещаемость, оценки, стрик (без чатов и решений)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import require_parent
from app.models.extras import Announcement, LessonAttendance
from app.models.homework import Homework, HomeworkStatus
from app.models.lesson import Lesson
from app.models.topic import UserTopicProgress
from app.models.user import ParentStudent, User
from app.models.xp import Streak
from app.deps import csrf_token_for
from app.services.gamification import level_title, next_level_info
from app.templating import get_templates

router = APIRouter(prefix="/parent", tags=["parent"])
templates = get_templates()
settings = get_settings()


def _children(db: Session, parent: User) -> list[User]:
    links = db.query(ParentStudent).filter(ParentStudent.parent_id == parent.id).all()
    kids = []
    for link in links:
        s = db.get(User, link.student_id)
        if s:
            kids.append(s)
    return kids


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def parent_home(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    parent: Annotated[User, Depends(require_parent)],
    child_id: int = 0,
):
    children = _children(db, parent)
    if not children:
        return templates.TemplateResponse(
            "parent/dashboard.html",
            {
                "request": request,
                "user": parent,
                "children": [],
                "child": None,
                "app_name": settings.app_name,
                "csrf_token": csrf_token_for(request),
            },
        )

    child = None
    if child_id:
        child = next((c for c in children if c.id == child_id), None)
    if not child:
        child = children[0]

    streak = db.query(Streak).filter(Streak.user_id == child.id).first()
    graded = (
        db.query(Homework)
        .filter(
            Homework.student_id == child.id,
            Homework.status == HomeworkStatus.GRADED,
        )
        .order_by(Homework.created_at.desc())
        .limit(15)
        .all()
    )
    # Оценки — только score, без text_answer и файлов
    grades = []
    for h in graded:
        grades.append(
            {
                "title": h.title,
                "score": h.submission.score if h.submission else None,
                "max_score": h.max_score,
                "due_at": h.due_at,
                "status": h.status.value,
            }
        )

    # Посещаемость из отметок преподавателя
    att_rows = (
        db.query(LessonAttendance)
        .filter(LessonAttendance.student_id == child.id)
        .order_by(LessonAttendance.marked_at.desc())
        .limit(20)
        .all()
    )
    attendance = []
    for a in att_rows:
        attendance.append(
            {
                "title": a.lesson.title if a.lesson else f"Урок #{a.lesson_id}",
                "date": a.lesson.scheduled_at if a.lesson else a.marked_at,
                "status": a.status,
            }
        )

    progress = (
        db.query(UserTopicProgress)
        .options(joinedload(UserTopicProgress.topic))
        .filter(UserTopicProgress.user_id == child.id)
        .all()
    )
    avg_progress = (
        round(sum(p.progress for p in progress) / len(progress), 0) if progress else 0
    )
    level_info = next_level_info(child.xp)
    announcements = (
        db.query(Announcement)
        .filter(
            Announcement.is_active.is_(True),
            Announcement.audience.in_(["all", "parents"]),
        )
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        "parent/dashboard.html",
        {
            "request": request,
            "user": parent,
            "children": children,
            "child": child,
            "streak": streak,
            "grades": grades,
            "attendance": attendance,
            "progress": progress,
            "avg_progress": avg_progress,
            "level_info": level_info,
            "level_title": level_title(child.level_key),
            "announcements": announcements,
            "app_name": settings.app_name,
            "csrf_token": csrf_token_for(request),
        },
    )
