"""Задание дня — стабильный «рандом» от даты + банка автопроверок."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.homework import Homework
from app.services.homework_check import parse_tasks, tasks_to_public


def pick_daily_challenge(db: Session, student_id: int | None = None) -> dict[str, Any] | None:
    """
    Выбрать одно задание на сегодня из автопроверок ДЗ.
    Если student_id задан — предпочитаем его ДЗ, иначе любые с auto_check.
    """
    q = db.query(Homework).filter(Homework.auto_check_json.isnot(None))
    if student_id:
        own = q.filter(Homework.student_id == student_id).all()
        pool_hw = own if own else q.limit(50).all()
    else:
        pool_hw = q.limit(50).all()

    bank: list[dict[str, Any]] = []
    for hw in pool_hw:
        for t in parse_tasks(hw.auto_check_json):
            bank.append(
                {
                    "homework_id": hw.id,
                    "homework_title": hw.title,
                    "task": t,
                }
            )

    if not bank:
        return None

    day_key = date.today().isoformat()
    digest = hashlib.sha256(f"{day_key}:{student_id or 0}".encode()).hexdigest()
    idx = int(digest[:8], 16) % len(bank)
    item = bank[idx]
    public = tasks_to_public(
        __import__("json").dumps([item["task"]], ensure_ascii=False)
    )
    return {
        "day": day_key,
        "homework_id": item["homework_id"],
        "homework_title": item["homework_title"],
        "task": public[0] if public else item["task"],
        "answer_hint": None,  # не показываем ответ
    }
