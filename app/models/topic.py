"""Темы / карта знаний."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Topic(Base):
    """Тема из карты знаний (дерево: parent_id)."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(String(32), default="math")  # math / informatics
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str] = mapped_column(String(64), default="book")
    color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parent: Mapped[Optional["Topic"]] = relationship(
        "Topic",
        remote_side="Topic.id",
        back_populates="children",
    )
    children: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="parent",
        order_by="Topic.order_index",
    )
    progress_records: Mapped[list["UserTopicProgress"]] = relationship(
        "UserTopicProgress",
        back_populates="topic",
    )


class UserTopicProgress(Base):
    """Прогресс ученика по теме (0–100%)."""

    __tablename__ = "user_topic_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    mastery: Mapped[str] = mapped_column(String(32), default="not_started")  # not_started/learning/practiced/mastered
    last_practiced: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="topic_progress")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="progress_records")
