"""Автопроверка простых заданий (тесты и поля ввода)."""

from __future__ import annotations

import json
from typing import Any


def parse_tasks(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


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
