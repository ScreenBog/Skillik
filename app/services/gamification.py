"""Геймификация: XP, уровни, стрик, достижения."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.achievement import Achievement, UserAchievement
from app.models.user import User
from app.models.xp import LEVELS, Streak, XPLog


def level_for_xp(xp: int) -> tuple[str, str]:
    """Вернуть (key, title) уровня по XP."""
    current = LEVELS[0]
    for key, title, threshold in LEVELS:
        if xp >= threshold:
            current = (key, title)
    return current


def next_level_info(xp: int) -> dict:
    """Информация о следующем уровне."""
    current_key, current_title = level_for_xp(xp)
    next_threshold = None
    next_title = None
    current_threshold = 0
    for i, (key, title, thr) in enumerate(LEVELS):
        if key == current_key:
            current_threshold = thr
            if i + 1 < len(LEVELS):
                next_threshold = LEVELS[i + 1][2]
                next_title = LEVELS[i + 1][1]
            break
    progress = 100.0
    if next_threshold is not None and next_threshold > current_threshold:
        progress = min(100.0, (xp - current_threshold) / (next_threshold - current_threshold) * 100)
    return {
        "level_key": current_key,
        "level_title": current_title,
        "xp": xp,
        "next_threshold": next_threshold,
        "next_title": next_title,
        "progress_pct": progress,
    }


def add_xp(db: Session, user: User, amount: int, reason: str, details: str | None = None) -> User:
    """Начислить или списать XP, обновить уровень."""
    user.xp = max(0, user.xp + amount)
    key, _ = level_for_xp(user.xp)
    user.level_key = key
    db.add(
        XPLog(
            user_id=user.id,
            amount=amount,
            reason=reason,
            details=details,
        )
    )
    db.flush()
    check_achievements(db, user)
    return user


def ensure_streak(db: Session, user: User) -> Streak:
    """Получить или создать запись стрика."""
    streak = db.query(Streak).filter(Streak.user_id == user.id).first()
    if not streak:
        streak = Streak(user_id=user.id)
        db.add(streak)
        db.flush()
    return streak


def _iso_week(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def record_activity(db: Session, user: User) -> Streak:
    """Отметить активность сегодня (стрик +1)."""
    streak = ensure_streak(db, user)
    today = date.today()
    if streak.last_activity_date == today:
        return streak

    if streak.last_activity_date is None:
        streak.current_streak = 1
    else:
        delta = (today - streak.last_activity_date).days
        if delta == 1:
            streak.current_streak += 1
        elif delta == 2 and streak.freeze_available:
            # Автозаморозка пропущенного дня (1 раз в неделю)
            week = _iso_week(today)
            if streak.freeze_used_week != week:
                streak.freeze_used_week = week
                streak.freeze_available = False
                streak.current_streak += 1
            else:
                streak.current_streak = 1
        else:
            streak.current_streak = 1

    streak.last_activity_date = today
    streak.longest_streak = max(streak.longest_streak, streak.current_streak)

    # Сброс freeze_available в новую неделю
    week = _iso_week(today)
    if streak.freeze_used_week and streak.freeze_used_week != week:
        streak.freeze_available = True

    db.flush()
    check_achievements(db, user)
    return streak


def freeze_streak(db: Session, user: User) -> tuple[bool, str]:
    """Ручная заморозка стрика на 1 день (1 раз в неделю)."""
    streak = ensure_streak(db, user)
    week = _iso_week(date.today())
    if not streak.freeze_available or streak.freeze_used_week == week:
        return False, "Заморозка уже использована на этой неделе"
    streak.freeze_used_week = week
    streak.freeze_available = False
    # Продлить last_activity как будто вчерашний день «закрыт»
    if streak.last_activity_date != date.today():
        streak.last_activity_date = date.today()
    db.flush()
    return True, "Стрик заморожен на сегодня"


def check_achievements(db: Session, user: User) -> list[Achievement]:
    """Проверить и выдать достижения."""
    earned: list[Achievement] = []
    all_ach = db.query(Achievement).filter(Achievement.is_active.is_(True)).all()
    have_ids = {
        ua.achievement_id
        for ua in db.query(UserAchievement).filter(UserAchievement.user_id == user.id).all()
    }
    streak = db.query(Streak).filter(Streak.user_id == user.id).first()
    from app.models.homework import Homework, HomeworkStatus

    hw_done = (
        db.query(Homework)
        .filter(
            Homework.student_id == user.id,
            Homework.status == HomeworkStatus.GRADED,
        )
        .count()
    )

    for ach in all_ach:
        if ach.id in have_ids:
            continue
        ok = False
        if ach.condition_type == "streak" and streak and streak.current_streak >= (ach.condition_value or 0):
            ok = True
        elif ach.condition_type == "homework_count" and hw_done >= (ach.condition_value or 0):
            ok = True
        elif ach.condition_type == "xp" and user.xp >= (ach.condition_value or 0):
            ok = True
        elif ach.condition_type == "level" and user.level_key == (ach.code.replace("level_", "") if False else None):
            # condition_value unused; code like level_expert
            pass
        elif ach.condition_type == "level_key":
            # condition stored in code value field via description — use condition_value as index
            keys = [k for k, _, _ in LEVELS]
            target = keys[min(ach.condition_value or 0, len(keys) - 1)]
            if user.level_key == target or LEVELS[keys.index(user.level_key)][2] >= LEVELS[keys.index(target)][2]:
                ok = True
        elif ach.condition_type == "manual":
            continue

        if ach.condition_type == "first_login" and user.last_login:
            ok = True

        if ok:
            db.add(UserAchievement(user_id=user.id, achievement_id=ach.id))
            if ach.xp_bonus:
                user.xp += ach.xp_bonus
                db.add(XPLog(user_id=user.id, amount=ach.xp_bonus, reason="achievement", details=ach.code))
            earned.append(ach)
    if earned:
        db.flush()
    return earned


def level_title(key: str) -> str:
    for k, title, _ in LEVELS:
        if k == key:
            return title
    return "Новичок"
