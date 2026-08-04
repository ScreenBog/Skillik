"""Jinja2: фильтры, подписи, flash-сообщения."""

from __future__ import annotations

from typing import Any

from fastapi.templating import Jinja2Templates

# Статусы ДЗ → русский
HW_STATUS: dict[str, str] = {
    "assigned": "Выдано",
    "in_progress": "В работе",
    "submitted": "На проверке",
    "graded": "Оценено",
    "overdue": "Просрочено",
    "deferred": "Отсрочено",
}

# Мастерство темы
MASTERY: dict[str, str] = {
    "not_started": "Не начато",
    "learning": "Изучаю",
    "practiced": "Практикую",
    "mastered": "Освоено",
}

# Статус урока
LESSON_STATUS: dict[str, str] = {
    "planned": "Запланирован",
    "done": "Проведён",
    "cancelled": "Отменён",
}

# Flash по ?ok= / ?error=
FLASH_OK: dict[str, str] = {
    "1": "Сохранено",
    "password": "Пароль изменён",
    "parent": "Родитель привязан",
    "file": "Файл загружен",
    "graded": "Оценка сохранена, XP начислен",
    "fb": "Спасибо за отзыв! +5 XP",
    "defer": "Срок ДЗ продлён на 1 день",
    "urgent": "Срочный вопрос отправлен",
    "freeze": "Стрик заморожен на сегодня",
    "practice": "Тренировка засчитана! +10 XP",
    "submitted": "Работа отправлена на проверку",
    "help": "Запрос помощи отправлен преподавателю",
    "attendance": "Посещаемость сохранена",
    "ok": "Готово",
}

FLASH_ERR: dict[str, str] = {
    "bad_password": "Неверный текущий пароль",
    "short": "Пароль слишком короткий (минимум 6 символов)",
    "no_defer": "Нет отсрочки в инвентаре — купите в магазине",
    "nomoney": "Недостаточно XP",
    "error": "Не удалось выполнить действие",
    "no_students": "Выберите хотя бы одного ученика или «Всем»",
    "empty": "Заполните текст",
}

ATTENDANCE: dict[str, str] = {
    "present": "Был",
    "absent": "Не был",
    "late": "Опоздал",
    "remote": "Онлайн",
}


def hw_status_label(value: Any) -> str:
    key = value.value if hasattr(value, "value") else str(value or "")
    return HW_STATUS.get(key, key)


def mastery_label(value: str | None) -> str:
    return MASTERY.get(value or "not_started", value or "—")


def lesson_status_label(value: str | None) -> str:
    return LESSON_STATUS.get(value or "", value or "—")


def attendance_label(value: str | None) -> str:
    return ATTENDANCE.get(value or "", value or "—")


def flash_messages(request) -> list[dict[str, str]]:
    """Список flash из query-параметров ok/error/msg."""
    msgs: list[dict[str, str]] = []
    try:
        qp = request.query_params
    except Exception:
        return msgs
    ok = qp.get("ok")
    if ok is not None:
        text = FLASH_OK.get(ok, FLASH_OK.get("1", "Готово"))
        if ok and ok not in FLASH_OK and ok not in ("1",):
            # кастомный текст не используем — безопасный дефолт
            text = FLASH_OK.get("1", "Готово")
        msgs.append({"type": "success", "text": text})
    err = qp.get("error") or (qp.get("msg") if qp.get("msg") in FLASH_ERR else None)
    if err:
        msgs.append({"type": "error", "text": FLASH_ERR.get(err, "Ошибка")})
    msg = qp.get("msg")
    if msg == "ok":
        msgs.append({"type": "success", "text": "Покупка успешна!"})
    elif msg in FLASH_ERR and not err:
        msgs.append({"type": "error", "text": FLASH_ERR[msg]})
    return msgs


def weekday_ru(dt) -> str:
    if not dt:
        return ""
    names = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    try:
        return names[dt.weekday()]
    except Exception:
        return ""


def avatar_emoji(key: str | None) -> str:
    from app.services.homework_check import avatar_emoji as _ae

    return _ae(key)


def setup_templates(templates: Jinja2Templates) -> Jinja2Templates:
    templates.env.filters["hw_status"] = hw_status_label
    templates.env.filters["mastery"] = mastery_label
    templates.env.filters["lesson_status"] = lesson_status_label
    templates.env.filters["attendance"] = attendance_label
    templates.env.filters["weekday_ru"] = weekday_ru
    templates.env.filters["avatar_emoji"] = avatar_emoji
    templates.env.globals["flash_messages"] = flash_messages
    templates.env.globals["HW_STATUS"] = HW_STATUS
    templates.env.globals["MASTERY"] = MASTERY
    templates.env.globals["ATTENDANCE"] = ATTENDANCE
    templates.env.globals["avatar_emoji"] = avatar_emoji
    return templates


def get_templates(directory: str = "app/templates") -> Jinja2Templates:
    """Общий фабричный метод для роутеров."""
    return setup_templates(Jinja2Templates(directory=directory))
