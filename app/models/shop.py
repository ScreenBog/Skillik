"""Магазин за XP."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ShopItem(Base):
    """Товар магазина."""

    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # avatar | frame | sticker | defer_hw | accent_color
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    price_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    # Значение: имя аватара, цвет #hex, "defer_1d" и т.п.
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[str] = mapped_column(String(64), default="gift")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    stock: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = бесконечно
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class UserPurchase(Base):
    """Покупка ученика."""

    __tablename__ = "user_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("shop_items.id", ondelete="CASCADE"))
    price_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)  # для одноразовых (defer)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="purchases")
    item: Mapped["ShopItem"] = relationship("ShopItem")
