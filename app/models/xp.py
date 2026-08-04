"""XP, уровни, стрик."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Пороги уровней (XP суммарный)
LEVELS = [
    ("novice", "Новичок", 0),
    ("student", "Ученик", 100),
    ("expert", "Знаток", 350),
    ("master", "Мастер", 800),
    ("legend", "Легенда", 1500),
]


class XPLog(Base):
    """Журнал начисления/списания XP."""

    __tablename__ = "xp_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # + или −
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="xp_logs")


class Streak(Base):
    """Стрик активности ученика (дни подряд)."""

    __tablename__ = "streaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Заморозка: 1 день в неделю
    freeze_used_week: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # ISO week "2026-W12"
    freeze_available: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="streak")
