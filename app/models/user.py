"""Пользователи: админ, ученик, родитель."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.achievement import UserAchievement
    from app.models.homework import Homework, HomeworkSubmission
    from app.models.message import Message, UrgentQuestion
    from app.models.shop import UserPurchase
    from app.models.topic import UserTopicProgress
    from app.models.xp import Streak, XPLog


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STUDENT = "student"
    PARENT = "parent"


class User(Base):
    """Учётная запись платформы."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, index=True)

    # Профиль
    avatar: Mapped[str] = mapped_column(String(128), default="default")
    avatar_frame: Mapped[str] = mapped_column(String(64), default="none")
    accent_color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    theme_preference: Mapped[str] = mapped_column(String(16), default="system")  # light/dark/system
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Геймификация
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level_key: Mapped[str] = mapped_column(String(32), default="novice")  # novice/student/expert/master/legend

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Связи
    homework_assigned: Mapped[list["Homework"]] = relationship(
        "Homework",
        back_populates="student",
        foreign_keys="Homework.student_id",
    )
    submissions: Mapped[list["HomeworkSubmission"]] = relationship(
        "HomeworkSubmission",
        back_populates="student",
        foreign_keys="HomeworkSubmission.student_id",
    )
    topic_progress: Mapped[list["UserTopicProgress"]] = relationship(
        "UserTopicProgress",
        back_populates="user",
    )
    achievements: Mapped[list["UserAchievement"]] = relationship(
        "UserAchievement",
        back_populates="user",
    )
    xp_logs: Mapped[list["XPLog"]] = relationship("XPLog", back_populates="user")
    streak: Mapped[Optional["Streak"]] = relationship(
        "Streak",
        back_populates="user",
        uselist=False,
    )
    purchases: Mapped[list["UserPurchase"]] = relationship(
        "UserPurchase",
        back_populates="user",
    )
    messages_sent: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="sender",
        foreign_keys="Message.sender_id",
    )
    messages_received: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="recipient",
        foreign_keys="Message.recipient_id",
    )
    urgent_questions: Mapped[list["UrgentQuestion"]] = relationship(
        "UrgentQuestion",
        back_populates="student",
        foreign_keys="UrgentQuestion.student_id",
    )

    # Родитель ↔ дети
    children_links: Mapped[list["ParentStudent"]] = relationship(
        "ParentStudent",
        back_populates="parent",
        foreign_keys="ParentStudent.parent_id",
    )
    parent_links: Mapped[list["ParentStudent"]] = relationship(
        "ParentStudent",
        back_populates="student",
        foreign_keys="ParentStudent.student_id",
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_student(self) -> bool:
        return self.role == UserRole.STUDENT

    @property
    def is_parent(self) -> bool:
        return self.role == UserRole.PARENT


class ParentStudent(Base):
    """Связь родителя с учеником (один родитель — несколько детей)."""

    __tablename__ = "parent_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parent: Mapped["User"] = relationship(
        "User",
        back_populates="children_links",
        foreign_keys=[parent_id],
    )
    student: Mapped["User"] = relationship(
        "User",
        back_populates="parent_links",
        foreign_keys=[student_id],
    )
