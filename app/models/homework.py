"""Домашние задания и сдачи."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.lesson import Lesson
    from app.models.topic import Topic
    from app.models.user import User


class HomeworkStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"
    OVERDUE = "overdue"
    DEFERRED = "deferred"  # отсрочка из магазина


class Homework(Base):
    """Домашнее задание (индивидуальное или на группу — student_id)."""

    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Автопроверка: JSON-описание заданий [{type, question, answer, options?}]
    auto_check_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
    )
    topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[HomeworkStatus] = mapped_column(
        Enum(HomeworkStatus),
        default=HomeworkStatus.ASSIGNED,
    )
    max_score: Mapped[float] = mapped_column(Float, default=5.0)
    xp_reward: Mapped[int] = mapped_column(Integer, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped["User"] = relationship(
        "User",
        back_populates="homework_assigned",
        foreign_keys=[student_id],
    )
    assigner: Mapped["User"] = relationship("User", foreign_keys=[assigned_by])
    lesson: Mapped[Optional["Lesson"]] = relationship("Lesson")
    topic: Mapped[Optional["Topic"]] = relationship("Topic")
    submission: Mapped[Optional["HomeworkSubmission"]] = relationship(
        "HomeworkSubmission",
        back_populates="homework",
        uselist=False,
        cascade="all, delete-orphan",
    )


class HomeworkSubmission(Base):
    """Сдача домашнего задания учеником."""

    __tablename__ = "homework_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    homework_id: Mapped[int] = mapped_column(
        ForeignKey("homeworks.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Ответы автопроверки JSON
    auto_answers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    teacher_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    graded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    homework: Mapped["Homework"] = relationship("Homework", back_populates="submission")
    student: Mapped["User"] = relationship(
        "User",
        back_populates="submissions",
        foreign_keys=[student_id],
    )
    grader: Mapped[Optional["User"]] = relationship("User", foreign_keys=[graded_by])
