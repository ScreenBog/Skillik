"""Уроки, файлы, шаблоны, привязка к темам."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.topic import Topic
    from app.models.user import User


class Lesson(Base):
    """Занятие (урок)."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # HTML/markdown текст
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    youtube_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    youtube_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # секунды таймкода
    status: Mapped[str] = mapped_column(String(32), default="planned")  # planned/done/cancelled
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    files: Mapped[list["LessonFile"]] = relationship(
        "LessonFile",
        back_populates="lesson",
        cascade="all, delete-orphan",
    )
    topics: Mapped[list["LessonTopic"]] = relationship(
        "LessonTopic",
        back_populates="lesson",
        cascade="all, delete-orphan",
    )
    # Ученики, привязанные к уроку (через промежуточную — упрощённо student_id nullable = всем)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student: Mapped[Optional["User"]] = relationship("User", foreign_keys=[student_id])


class LessonFile(Base):
    """Прикреплённый файл к уроку."""

    __tablename__ = "lesson_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="files")


class LessonTopic(Base):
    """M2M: урок ↔ тема."""

    __tablename__ = "lesson_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="topics")
    topic: Mapped["Topic"] = relationship("Topic")


class LessonTemplate(Base):
    """Шаблон урока для быстрого создания."""

    __tablename__ = "lesson_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(String(32), default="math")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
