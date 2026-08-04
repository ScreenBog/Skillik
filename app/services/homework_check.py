"""Автопроверка простых заданий (тесты и поля ввода) + импорт из JSON нейросети."""

from __future__ import annotations

import json
import re
from typing import Any

# Максимум заданий в форме админки
MAX_AUTO_QUESTIONS = 20


def parse_tasks(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        # полный пакет { tasks: [...] }
        if isinstance(data, dict) and isinstance(data.get("tasks"), list):
            return data["tasks"]
        return []
    except json.JSONDecodeError:
        return []


def strip_code_fences(raw: str) -> str:
    """Убрать ```json ... ``` обёртку, если нейросеть её добавила."""
    text = (raw or "").strip()
    if not text:
        return ""
    fence = re.match(r"^```(?:json|JSON)?\s*\n?(.*?)```\s*$", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    # иногда fence только в начале
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _normalize_task(raw_task: Any, index: int) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw_task, dict):
        return None, f"Задание #{index + 1}: ожидается объект, не {type(raw_task).__name__}"
    question = str(raw_task.get("question", "")).strip()
    if not question:
        return None, f"Задание #{index + 1}: пустой question"
    answer = str(raw_task.get("answer", "")).strip()
    if not answer:
        return None, f"Задание #{index + 1}: пустой answer"
    ttype = str(raw_task.get("type", "input") or "input").strip().lower()
    if ttype not in ("input", "test"):
        return None, f"Задание #{index + 1}: type должен быть input или test (сейчас «{ttype}»)"
    try:
        points = float(raw_task.get("points", 1) or 1)
    except (TypeError, ValueError):
        points = 1.0
    if points <= 0:
        points = 1.0
    task: dict[str, Any] = {
        "id": str(raw_task.get("id", index + 1)),
        "type": ttype,
        "question": question,
        "answer": answer,
        "points": points,
    }
    if ttype == "test":
        opts = raw_task.get("options")
        if isinstance(opts, str):
            opts = [o.strip() for o in opts.replace("|", ";").split(";") if o.strip()]
        if not isinstance(opts, list) or len(opts) < 2:
            return None, f"Задание #{index + 1}: для test нужны options (минимум 2 варианта)"
        task["options"] = [str(o).strip() for o in opts if str(o).strip()]
        # ответ должен совпадать с одним из вариантов (или |список)
        allowed = {o.lower() for o in task["options"]}
        ans_ok = any(a.strip().lower() in allowed for a in answer.split("|"))
        if not ans_ok:
            return None, (
                f"Задание #{index + 1}: answer «{answer}» не входит в options"
            )
    return task, None


def import_from_ai_json(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Импорт пакета ДЗ от нейросети.

    Поддерживает:
      1) Полный объект { title, description, max_score, xp_reward, tasks: [...] }
      2) Просто массив tasks: [ {...}, ... ]
      3) Markdown-обёртку ```json ... ```

    Returns: (data, errors). data=None если критическая ошибка.
    """
    errors: list[str] = []
    text = strip_code_fences(raw)
    if not text:
        return None, ["Пустой текст — вставьте JSON от нейросети"]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [f"Невалидный JSON: {e.msg} (строка {e.lineno}, позиция {e.colno})"]

    title = ""
    description = ""
    max_score: float | None = None
    xp_reward: int | None = None
    tasks_raw: list[Any] = []

    if isinstance(data, list):
        tasks_raw = data
    elif isinstance(data, dict):
        title = str(data.get("title", "") or "").strip()
        description = str(data.get("description", "") or "").strip()
        if "max_score" in data and data["max_score"] is not None:
            try:
                max_score = float(data["max_score"])
            except (TypeError, ValueError):
                errors.append("max_score должен быть числом")
        if "xp_reward" in data and data["xp_reward"] is not None:
            try:
                xp_reward = int(data["xp_reward"])
            except (TypeError, ValueError):
                errors.append("xp_reward должен быть целым числом")
        if "tasks" not in data:
            # одиночное задание?
            if data.get("question") and data.get("answer"):
                tasks_raw = [data]
            else:
                return None, errors + ["Не найден блок tasks (массив заданий)"]
        else:
            if not isinstance(data["tasks"], list):
                return None, errors + ["tasks должен быть массивом"]
            tasks_raw = data["tasks"]
    else:
        return None, ["JSON должен быть объектом {...} или массивом заданий [...]"]

    if not tasks_raw:
        return None, errors + ["Список tasks пуст — добавьте хотя бы одно задание"]

    if len(tasks_raw) > MAX_AUTO_QUESTIONS:
        errors.append(
            f"Слишком много заданий ({len(tasks_raw)}). Максимум {MAX_AUTO_QUESTIONS} — лишние обрезаны"
        )
        tasks_raw = tasks_raw[:MAX_AUTO_QUESTIONS]

    tasks: list[dict[str, Any]] = []
    for i, raw_task in enumerate(tasks_raw):
        task, err = _normalize_task(raw_task, i)
        if err:
            errors.append(err)
            continue
        if task:
            tasks.append(task)

    if not tasks:
        return None, errors + ["Ни одно задание не прошло проверку"]

    # max_score по умолчанию = сумма points
    sum_points = sum(float(t.get("points", 1)) for t in tasks)
    if max_score is None:
        max_score = sum_points if sum_points > 0 else 5.0
    if xp_reward is None:
        xp_reward = 20

    result = {
        "title": title or "Домашнее задание",
        "description": description,
        "max_score": max_score,
        "xp_reward": xp_reward,
        "tasks": tasks,
        "tasks_json": json.dumps(tasks, ensure_ascii=False),
        "tasks_count": len(tasks),
    }
    return result, errors


def check_answers(
    tasks_json: str | None,
    answers: dict[str, str],
) -> tuple[float, float, list[dict[str, Any]]]:
    """
    Проверить ответы.
    Returns: (score, max_score, details)
    tasks: [{id, type: test|input, question, answer, options?, points?}]
    """
    tasks = parse_tasks(tasks_json)
    if not tasks:
        return 0.0, 0.0, []

    total = 0.0
    got = 0.0
    details: list[dict[str, Any]] = []

    for i, task in enumerate(tasks):
        tid = str(task.get("id", i))
        points = float(task.get("points", 1))
        total += points
        correct = str(task.get("answer", "")).strip().lower()
        user_ans = str(answers.get(tid, answers.get(f"q_{i}", ""))).strip().lower()
        is_ok = user_ans == correct if correct else False
        # Допускаем несколько правильных через |
        if not is_ok and "|" in correct:
            is_ok = user_ans in [a.strip() for a in correct.split("|")]
        if is_ok:
            got += points
        details.append(
            {
                "id": tid,
                "question": task.get("question", ""),
                "user_answer": user_ans,
                "correct": is_ok,
                "points": points if is_ok else 0,
            }
        )

    return got, total, details


def tasks_to_public(tasks_json: str | None) -> list[dict[str, Any]]:
    """Версия заданий без правильных ответов (для ученика)."""
    public = []
    for i, task in enumerate(parse_tasks(tasks_json)):
        public.append(
            {
                "id": str(task.get("id", i)),
                "type": task.get("type", "input"),
                "question": task.get("question", ""),
                "options": task.get("options"),
                "points": task.get("points", 1),
            }
        )
    return public


def build_tasks_from_form(form: Any) -> list[dict[str, Any]]:
    """
    Собрать задания из полей формы:
      aq_question_0, aq_answer_0, aq_type_0, aq_points_0, aq_options_0
    """
    tasks: list[dict[str, Any]] = []
    for i in range(MAX_AUTO_QUESTIONS):
        q = str(form.get(f"aq_question_{i}", "") or "").strip()
        if not q:
            continue
        ans = str(form.get(f"aq_answer_{i}", "") or "").strip()
        ttype = str(form.get(f"aq_type_{i}", "input") or "input").strip()
        if ttype not in ("input", "test"):
            ttype = "input"
        try:
            points = float(form.get(f"aq_points_{i}", 1) or 1)
        except (TypeError, ValueError):
            points = 1.0
        options_raw = str(form.get(f"aq_options_{i}", "") or "").strip()
        task: dict[str, Any] = {
            "id": str(i + 1),
            "type": ttype,
            "question": q,
            "answer": ans,
            "points": points,
        }
        if ttype == "test" and options_raw:
            opts = [o.strip() for o in options_raw.replace("|", ";").split(";") if o.strip()]
            if opts:
                task["options"] = opts
        tasks.append(task)
    return tasks


def tasks_to_json(tasks: list[dict[str, Any]]) -> str | None:
    if not tasks:
        return None
    return json.dumps(tasks, ensure_ascii=False)


# Визуальные аватары магазина
AVATAR_EMOJI: dict[str, str] = {
    "default": "🙂",
    "fox": "🦊",
    "owl": "🦉",
    "robot": "🤖",
    "cat": "🐱",
    "bear": "🐻",
    "star": "⭐",
}


def avatar_emoji(key: str | None) -> str:
    return AVATAR_EMOJI.get(key or "default", "🙂")
