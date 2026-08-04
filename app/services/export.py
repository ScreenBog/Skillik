"""Экспорт данных (CSV)."""

from __future__ import annotations

import csv
import io
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.homework import Homework, HomeworkStatus
from app.models.user import User, UserRole


def export_students_csv(db: Session) -> str:
    """CSV список учеников с XP и уровнем."""
    students = (
        db.query(User)
        .filter(User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["id", "username", "full_name", "xp", "level", "active", "blocked"])
    for s in students:
        writer.writerow(
            [
                s.id,
                s.username,
                s.full_name,
                s.xp,
                s.level_key,
                int(s.is_active),
                int(s.is_blocked),
            ]
        )
    return buf.getvalue()


def export_homework_csv(db: Session, student_id: int | None = None) -> str:
    q = db.query(Homework)
    if student_id:
        q = q.filter(Homework.student_id == student_id)
    rows = q.order_by(Homework.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["id", "title", "student_id", "status", "due_at", "score"])
    for h in rows:
        score = h.submission.score if h.submission else ""
        writer.writerow(
            [
                h.id,
                h.title,
                h.student_id,
                h.status.value if isinstance(h.status, HomeworkStatus) else h.status,
                h.due_at.isoformat() if h.due_at else "",
                score,
            ]
        )
    return buf.getvalue()
