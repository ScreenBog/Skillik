"""Доп. фичи: объявления, блокнот, посещаемость, запросы помощи."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.homework import Homework
    from app.models.lesson import Lesson
    from app.models.topic import Topic
    from app.models.user import User


class Announcement(Base):
    """Объявление преподавателя (лента на главной)."""

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # all | students | parents
    audience: Mapped[str] = mapped_column(String(32), default="all")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentNote(Base):
    """Личный блокнот ученика (формулы, шпаргалки, мысли)."""

    __tablename__ = "student_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    color: Mapped[str] = mapped_column(String(16), default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    topic: Mapped[Optional["Topic"]] = relationship("Topic")


class LessonAttendance(Base):
    """Посещаемость урока."""

    __tablename__ = "lesson_attendance"
    __table_args__ = (UniqueConstraint("lesson_id", "student_id", name="uq_attendance_lesson_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # present | absent | late | remote
    status: Mapped[str] = mapped_column(String(16), default="present")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    marked_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lesson: Mapped["Lesson"] = relationship("Lesson")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])


class HelpRequest(Base):
    """Ученик просит помощь по ДЗ (видно админу)."""

    __tablename__ = "help_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    homework_id: Mapped[int] = mapped_column(ForeignKey("homeworks.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # open | resolved
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    teacher_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    homework: Mapped["Homework"] = relationship("Homework")
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
