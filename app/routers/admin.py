"""Админ-панель репетитора."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import require_admin, verify_csrf_form
from app.models.feedback import LessonFeedback
from app.models.homework import Homework, HomeworkStatus, HomeworkSubmission
from app.models.lesson import Lesson, LessonFile, LessonTemplate, LessonTopic
from app.models.message import Message, UrgentQuestion
from app.models.shop import ShopItem
from app.models.topic import Topic, UserTopicProgress
from app.models.user import ParentStudent, User, UserRole
from app.models.xp import Streak
from app.deps import csrf_token_for
from app.security import hash_password, sanitize_filename
from app.services.export import export_homework_csv, export_students_csv
from app.services.gamification import add_xp, level_title
from app.services.homework_check import (
    MAX_AUTO_QUESTIONS,
    build_tasks_from_form,
    import_from_ai_json,
    tasks_to_json,
)
from app.templating import get_templates

router = APIRouter(prefix="/admin", tags=["admin"])
templates = get_templates()
settings = get_settings()

_AI_HW_PROMPT = """Сгенерируй домашнее задание по математике / информатике для 5–7 класса.

Тема: [сюда тему]
Класс: [5/6/7]
Количество заданий: 5–8
Сложность: средняя

Верни ТОЛЬКО валидный JSON в таком формате (без markdown и пояснений):

{
  "title": "...",
  "description": "...",
  "max_score": 5,
  "xp_reward": 25,
  "tasks": [
    {
      "type": "input",
      "question": "текст вопроса",
      "answer": "правильный ответ (несколько через |)",
      "points": 1
    },
    {
      "type": "test",
      "question": "текст вопроса",
      "options": ["вариант1", "вариант2", "вариант3"],
      "answer": "вариант1",
      "points": 1
    }
  ]
}

Правила:
- type: "input" (вписать) или "test" (выбор)
- answer: правильный ответ; несколько допустимых через |
- options: только для test
- points: баллы (по умолчанию 1)
"""


def _ctx(request: Request, user: User, **kwargs):
    return {
        "request": request,
        "user": user,
        "csrf_token": csrf_token_for(request),
        "app_name": settings.app_name,
        **kwargs,
    }


def _save_upload(file: UploadFile, subdir: str = "lessons") -> tuple[str, str, int]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = settings.upload_dir / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    original = sanitize_filename(file.filename or "file")
    ext = Path(original).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise ValueError(f"Тип файла не разрешён: {ext}")
    stored = f"{secrets.token_hex(8)}_{original}"
    path = dest_dir / stored
    content = file.file.read()
    max_b = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_b:
        raise ValueError("Файл слишком большой")
    path.write_bytes(content)
    return f"{subdir}/{stored}", original, len(content)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    students_n = db.query(User).filter(User.role == UserRole.STUDENT).count()
    open_hw = db.query(Homework).filter(Homework.status == HomeworkStatus.SUBMITTED).count()
    urgent = db.query(UrgentQuestion).filter(UrgentQuestion.status == "open").count()
    unread = (
        db.query(Message)
        .filter(Message.recipient_id == admin.id, Message.is_read.is_(False))
        .count()
    )
    upcoming = (
        db.query(Lesson)
        .filter(Lesson.scheduled_at.isnot(None))
        .order_by(Lesson.scheduled_at.asc())
        .limit(5)
        .all()
    )
    recent_submissions = (
        db.query(HomeworkSubmission)
        .order_by(HomeworkSubmission.submitted_at.desc())
        .limit(8)
        .all()
    )
    return templates.TemplateResponse(
        "admin/dashboard.html",
        _ctx(
            request,
            admin,
            students_n=students_n,
            open_hw=open_hw,
            urgent=urgent,
            unread=unread,
            upcoming=upcoming,
            recent_submissions=recent_submissions,
        ),
    )


# ——— Ученики ———


@router.get("/students", response_class=HTMLResponse)
async def students_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    students = (
        db.query(User)
        .filter(User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    return templates.TemplateResponse(
        "admin/students.html",
        _ctx(request, admin, students=students, level_title=level_title),
    )


@router.get("/students/new", response_class=HTMLResponse)
async def student_new_form(
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
):
    return templates.TemplateResponse(
        "admin/student_form.html",
        _ctx(request, admin, student=None, generated_password=None),
    )


@router.post("/students/new")
async def student_create(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    full_name: Annotated[str, Form()],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()] = "",
    email: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    pwd = password.strip() or secrets.token_urlsafe(8)
    if db.query(User).filter(User.username == username.strip()).first():
        return templates.TemplateResponse(
            "admin/student_form.html",
            _ctx(
                request,
                admin,
                student=None,
                error="Логин уже занят",
                generated_password=None,
            ),
            status_code=400,
        )
    u = User(
        username=username.strip(),
        full_name=full_name.strip(),
        email=email.strip() or None,
        password_hash=hash_password(pwd),
        role=UserRole.STUDENT,
    )
    db.add(u)
    db.flush()
    db.add(Streak(user_id=u.id))
    db.commit()
    return templates.TemplateResponse(
        "admin/student_created.html",
        _ctx(request, admin, student=u, password=pwd),
    )


@router.get("/students/{student_id}", response_class=HTMLResponse)
async def student_detail(
    student_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    student = db.get(User, student_id)
    if not student or student.role != UserRole.STUDENT:
        return RedirectResponse("/admin/students", status_code=302)
    hw = (
        db.query(Homework)
        .filter(Homework.student_id == student_id)
        .order_by(Homework.created_at.desc())
        .limit(20)
        .all()
    )
    progress = (
        db.query(UserTopicProgress)
        .options(joinedload(UserTopicProgress.topic))
        .filter(UserTopicProgress.user_id == student_id)
        .all()
    )
    streak = db.query(Streak).filter(Streak.user_id == student_id).first()
    return templates.TemplateResponse(
        "admin/student_detail.html",
        _ctx(
            request,
            admin,
            student=student,
            homeworks=hw,
            progress=progress,
            streak=streak,
            level_title=level_title,
        ),
    )


@router.post("/students/{student_id}/edit")
async def student_edit(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()] = "",
    is_blocked: Annotated[str, Form()] = "",
    new_password: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    student = db.get(User, student_id)
    if not student or student.role != UserRole.STUDENT:
        return RedirectResponse("/admin/students", status_code=302)
    student.full_name = full_name.strip()
    student.email = email.strip() or None
    student.is_blocked = is_blocked == "on"
    if new_password.strip():
        student.password_hash = hash_password(new_password.strip())
    db.commit()
    return RedirectResponse(f"/admin/students/{student_id}?ok=1", status_code=302)


@router.post("/students/{student_id}/parent")
async def link_parent(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    parent_username: Annotated[str, Form()],
    parent_password: Annotated[str, Form()] = "",
    parent_name: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    student = db.get(User, student_id)
    if not student:
        return RedirectResponse("/admin/students", status_code=302)
    parent = db.query(User).filter(User.username == parent_username.strip()).first()
    if not parent:
        pwd = parent_password.strip() or secrets.token_urlsafe(8)
        parent = User(
            username=parent_username.strip(),
            full_name=parent_name.strip() or f"Родитель {student.full_name}",
            password_hash=hash_password(pwd),
            role=UserRole.PARENT,
        )
        db.add(parent)
        db.flush()
    exists = (
        db.query(ParentStudent)
        .filter(
            ParentStudent.parent_id == parent.id,
            ParentStudent.student_id == student_id,
        )
        .first()
    )
    if not exists:
        db.add(ParentStudent(parent_id=parent.id, student_id=student_id))
    db.commit()
    return RedirectResponse(f"/admin/students/{student_id}?ok=parent", status_code=302)


# ——— Уроки ———


@router.get("/lessons", response_class=HTMLResponse)
async def lessons_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    lessons = db.query(Lesson).order_by(Lesson.scheduled_at.desc().nullslast()).all()
    return templates.TemplateResponse(
        "admin/lessons.html",
        _ctx(request, admin, lessons=lessons),
    )


@router.get("/lessons/new", response_class=HTMLResponse)
async def lesson_new(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    template_id: int = 0,
):
    topics = db.query(Topic).filter(Topic.parent_id.isnot(None)).order_by(Topic.title).all()
    students = db.query(User).filter(User.role == UserRole.STUDENT, User.is_active.is_(True)).all()
    templates_list = db.query(LessonTemplate).order_by(LessonTemplate.title).all()
    # Prefill из шаблона
    prefill = None
    if template_id:
        tpl = db.get(LessonTemplate, template_id)
        if tpl:
            prefill = {
                "title": tpl.title,
                "description": tpl.description or "",
                "content": tpl.content or "",
            }
    return templates.TemplateResponse(
        "admin/lesson_form.html",
        _ctx(
            request,
            admin,
            lesson=None,
            topics=topics,
            students=students,
            templates_list=templates_list,
            prefill=prefill,
            selected_template_id=template_id or None,
        ),
    )


@router.post("/lessons/new")
async def lesson_create(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
    scheduled_at: Annotated[str, Form()] = "",
    duration_minutes: Annotated[int, Form()] = 60,
    youtube_url: Annotated[str, Form()] = "",
    youtube_start: Annotated[str, Form()] = "",
    student_id: Annotated[str, Form()] = "",
    topic_ids: Annotated[list[str], Form()] = [],
    is_published: Annotated[str, Form()] = "",
    status: Annotated[str, Form()] = "planned",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    lesson = Lesson(
        title=title.strip(),
        description=description.strip() or None,
        content=content.strip() or None,
        duration_minutes=duration_minutes,
        youtube_url=youtube_url.strip() or None,
        youtube_start=int(youtube_start) if youtube_start.strip().isdigit() else None,
        student_id=int(student_id) if student_id.strip().isdigit() else None,
        is_published=is_published == "on",
        status=status,
        created_by=admin.id,
    )
    if scheduled_at.strip():
        try:
            lesson.scheduled_at = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass
    db.add(lesson)
    db.flush()
    for tid in topic_ids:
        if tid.isdigit():
            db.add(LessonTopic(lesson_id=lesson.id, topic_id=int(tid)))
    db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson.id}", status_code=302)


@router.get("/lessons/{lesson_id}", response_class=HTMLResponse)
async def lesson_detail(
    lesson_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        return RedirectResponse("/admin/lessons", status_code=302)
    topics = db.query(Topic).filter(Topic.parent_id.isnot(None)).order_by(Topic.title).all()
    students = db.query(User).filter(User.role == UserRole.STUDENT).all()
    feedbacks = db.query(LessonFeedback).filter(LessonFeedback.lesson_id == lesson_id).all()
    return templates.TemplateResponse(
        "admin/lesson_form.html",
        _ctx(
            request,
            admin,
            lesson=lesson,
            topics=topics,
            students=students,
            templates_list=[],
            feedbacks=feedbacks,
        ),
    )


@router.post("/lessons/{lesson_id}")
async def lesson_update(
    lesson_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
    scheduled_at: Annotated[str, Form()] = "",
    duration_minutes: Annotated[int, Form()] = 60,
    youtube_url: Annotated[str, Form()] = "",
    youtube_start: Annotated[str, Form()] = "",
    student_id: Annotated[str, Form()] = "",
    topic_ids: Annotated[list[str], Form()] = [],
    is_published: Annotated[str, Form()] = "",
    status: Annotated[str, Form()] = "planned",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        return RedirectResponse("/admin/lessons", status_code=302)
    lesson.title = title.strip()
    lesson.description = description.strip() or None
    lesson.content = content.strip() or None
    lesson.duration_minutes = duration_minutes
    lesson.youtube_url = youtube_url.strip() or None
    lesson.youtube_start = int(youtube_start) if youtube_start.strip().isdigit() else None
    lesson.student_id = int(student_id) if student_id.strip().isdigit() else None
    lesson.is_published = is_published == "on"
    lesson.status = status
    if scheduled_at.strip():
        try:
            lesson.scheduled_at = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass
    else:
        lesson.scheduled_at = None
    db.query(LessonTopic).filter(LessonTopic.lesson_id == lesson_id).delete()
    for tid in topic_ids:
        if tid.isdigit():
            db.add(LessonTopic(lesson_id=lesson.id, topic_id=int(tid)))
    db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}?ok=1", status_code=302)


@router.post("/lessons/{lesson_id}/upload")
async def lesson_upload(
    lesson_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    file: Annotated[UploadFile, File()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        return RedirectResponse("/admin/lessons", status_code=302)
    try:
        stored, original, size = _save_upload(file, "lessons")
    except ValueError as e:
        return RedirectResponse(f"/admin/lessons/{lesson_id}?error={e}", status_code=302)
    db.add(
        LessonFile(
            lesson_id=lesson_id,
            filename=stored,
            original_name=original,
            content_type=file.content_type,
            size_bytes=size,
        )
    )
    db.commit()
    return RedirectResponse(f"/admin/lessons/{lesson_id}?ok=file", status_code=302)


# ——— ДЗ ———


@router.get("/homework", response_class=HTMLResponse)
async def homework_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    status_filter: str = "",
):
    q = db.query(Homework).order_by(Homework.created_at.desc())
    if status_filter:
        try:
            q = q.filter(Homework.status == HomeworkStatus(status_filter))
        except ValueError:
            pass
    items = q.limit(100).all()
    return templates.TemplateResponse(
        "admin/homework.html",
        _ctx(request, admin, items=items, status_filter=status_filter),
    )


@router.get("/homework/new", response_class=HTMLResponse)
async def homework_new(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    students = db.query(User).filter(User.role == UserRole.STUDENT, User.is_blocked.is_(False)).all()
    topics = db.query(Topic).filter(Topic.parent_id.isnot(None)).all()
    lessons = db.query(Lesson).order_by(Lesson.created_at.desc()).limit(50).all()
    return templates.TemplateResponse(
        "admin/homework_form.html",
        _ctx(
            request,
            admin,
            students=students,
            topics=topics,
            lessons=lessons,
            max_aq=MAX_AUTO_QUESTIONS,
            ai_prompt_example=_AI_HW_PROMPT,
        ),
    )


@router.post("/homework/parse-json")
async def homework_parse_json(
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    raw_json: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    """Разобрать JSON от нейросети → структурированные данные для формы."""
    from app.deps import verify_csrf
    from app.config import get_settings as gs

    s = gs()
    cookie = request.cookies.get(s.csrf_cookie_name, "")
    if not cookie or "." not in cookie:
        return {"ok": False, "errors": ["CSRF: обновите страницу"]}
    raw_c, sig = cookie.rsplit(".", 1)
    if not verify_csrf(raw_c, sig) or raw_c != csrf_token:
        return {"ok": False, "errors": ["CSRF: токен не совпадает, обновите страницу"]}

    data, errors = import_from_ai_json(raw_json)
    if data is None:
        return {"ok": False, "errors": errors or ["Не удалось разобрать JSON"]}
    # warnings = некритичные errors при успешном парсе
    return {
        "ok": True,
        "warnings": errors,
        "data": {
            "title": data["title"],
            "description": data["description"],
            "max_score": data["max_score"],
            "xp_reward": data["xp_reward"],
            "tasks": data["tasks"],
            "tasks_count": data["tasks_count"],
            "tasks_json": data["tasks_json"],
        },
    }


@router.post("/homework/new")
async def homework_create(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    student_ids: Annotated[list[str], Form()] = [],
    all_students: Annotated[str, Form()] = "",
    due_at: Annotated[str, Form()] = "",
    max_score: Annotated[float, Form()] = 5.0,
    xp_reward: Annotated[int, Form()] = 20,
    topic_id: Annotated[str, Form()] = "",
    lesson_id: Annotated[str, Form()] = "",
    auto_check_json: Annotated[str, Form()] = "",
    ai_package_json: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    ids: list[int] = []
    if all_students == "on":
        ids = [u.id for u in db.query(User).filter(User.role == UserRole.STUDENT, User.is_blocked.is_(False))]
    else:
        ids = [int(x) for x in student_ids if x.isdigit()]

    due = None
    if due_at.strip():
        try:
            due = datetime.fromisoformat(due_at)
        except ValueError:
            pass

    form = await request.form()
    tasks = build_tasks_from_form(form)
    ac = tasks_to_json(tasks)

    # Пакет от нейросети (полный JSON) — приоритет, если поля формы пусты
    if not ac and ai_package_json.strip():
        imported, _errs = import_from_ai_json(ai_package_json)
        if imported:
            ac = imported["tasks_json"]
            if not title.strip() or title.strip() == "Домашнее задание":
                title = imported["title"]
            if not description.strip():
                description = imported["description"]
            if imported.get("max_score"):
                max_score = float(imported["max_score"])
            if imported.get("xp_reward"):
                xp_reward = int(imported["xp_reward"])

    if not ac and auto_check_json.strip():
        imported, _errs = import_from_ai_json(auto_check_json)
        if imported:
            ac = imported["tasks_json"]
        else:
            try:
                parsed = json.loads(auto_check_json)
                if isinstance(parsed, list):
                    ac = auto_check_json.strip()
            except json.JSONDecodeError:
                ac = None

    if not ids:
        return RedirectResponse("/admin/homework/new?error=no_students", status_code=302)

    for sid in ids:
        hw = Homework(
            title=title.strip(),
            description=description.strip() or None,
            student_id=sid,
            assigned_by=admin.id,
            due_at=due,
            max_score=max_score,
            xp_reward=xp_reward,
            topic_id=int(topic_id) if topic_id.isdigit() else None,
            lesson_id=int(lesson_id) if lesson_id.isdigit() else None,
            auto_check_json=ac,
        )
        db.add(hw)
    db.commit()
    return RedirectResponse("/admin/homework?ok=1", status_code=302)


@router.get("/homework/{hw_id}/grade", response_class=HTMLResponse)
async def homework_grade_form(
    hw_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    hw = db.get(Homework, hw_id)
    if not hw:
        return RedirectResponse("/admin/homework", status_code=302)
    return templates.TemplateResponse(
        "admin/homework_grade.html",
        _ctx(request, admin, hw=hw),
    )


@router.post("/homework/{hw_id}/grade")
async def homework_grade(
    hw_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    score: Annotated[float, Form()],
    teacher_comment: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    hw = db.get(Homework, hw_id)
    if not hw:
        return RedirectResponse("/admin/homework", status_code=302)
    sub = hw.submission
    if not sub:
        sub = HomeworkSubmission(homework_id=hw.id, student_id=hw.student_id, text_answer="(оценка без сдачи)")
        db.add(sub)
        db.flush()
    sub.score = score
    sub.teacher_comment = teacher_comment.strip() or None
    sub.graded_at = datetime.utcnow()
    sub.graded_by = admin.id
    hw.status = HomeworkStatus.GRADED
    student = db.get(User, hw.student_id)
    if student:
        add_xp(db, student, hw.xp_reward, "homework_graded", f"ДЗ #{hw.id}")
        if hw.topic_id:
            prog = (
                db.query(UserTopicProgress)
                .filter(
                    UserTopicProgress.user_id == student.id,
                    UserTopicProgress.topic_id == hw.topic_id,
                )
                .first()
            )
            if not prog:
                prog = UserTopicProgress(user_id=student.id, topic_id=hw.topic_id, progress=0)
                db.add(prog)
            prog.progress = min(100.0, prog.progress + 15)
            if prog.progress >= 80:
                prog.mastery = "mastered"
            elif prog.progress >= 40:
                prog.mastery = "practiced"
            else:
                prog.mastery = "learning"
            prog.last_practiced = datetime.utcnow()
    db.commit()
    return RedirectResponse("/admin/homework?ok=graded", status_code=302)


# ——— Темы ———


@router.get("/topics", response_class=HTMLResponse)
async def topics_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    roots = db.query(Topic).filter(Topic.parent_id.is_(None)).order_by(Topic.order_index).all()
    return templates.TemplateResponse(
        "admin/topics.html",
        _ctx(request, admin, roots=roots),
    )


@router.post("/topics/new")
async def topic_create(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form()],
    slug: Annotated[str, Form()],
    subject: Annotated[str, Form()] = "math",
    parent_id: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    t = Topic(
        title=title.strip(),
        slug=slug.strip().lower().replace(" ", "-"),
        subject=subject,
        parent_id=int(parent_id) if parent_id.isdigit() else None,
        description=description.strip() or None,
    )
    db.add(t)
    db.commit()
    return RedirectResponse("/admin/topics?ok=1", status_code=302)


# ——— Сообщения ———


@router.get("/messages", response_class=HTMLResponse)
async def messages(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    with_user: int = 0,
):
    students = db.query(User).filter(User.role == UserRole.STUDENT).order_by(User.full_name).all()
    thread: list[Message] = []
    peer = None
    if with_user:
        peer = db.get(User, with_user)
        thread = (
            db.query(Message)
            .filter(
                ((Message.sender_id == admin.id) & (Message.recipient_id == with_user))
                | ((Message.sender_id == with_user) & (Message.recipient_id == admin.id))
            )
            .order_by(Message.created_at.asc())
            .all()
        )
        for m in thread:
            if m.recipient_id == admin.id and not m.is_read:
                m.is_read = True
        db.commit()
    urgent = (
        db.query(UrgentQuestion)
        .filter(UrgentQuestion.status == "open")
        .order_by(UrgentQuestion.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "admin/messages.html",
        _ctx(request, admin, students=students, thread=thread, peer=peer, urgent=urgent),
    )


@router.post("/messages/send")
async def messages_send(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    recipient_id: Annotated[int, Form()],
    body: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    if body.strip():
        db.add(Message(sender_id=admin.id, recipient_id=recipient_id, body=body.strip()))
        db.commit()
    return RedirectResponse(f"/admin/messages?with_user={recipient_id}", status_code=302)


@router.post("/urgent/{qid}/answer")
async def urgent_answer(
    qid: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    answer: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    q = db.get(UrgentQuestion, qid)
    if q:
        q.answer = answer.strip()
        q.status = "answered"
        q.answered_by = admin.id
        q.answered_at = datetime.utcnow()
        db.commit()
    return RedirectResponse("/admin/messages", status_code=302)


# ——— Магазин ———


@router.get("/shop", response_class=HTMLResponse)
async def shop_admin(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    items = db.query(ShopItem).order_by(ShopItem.sort_order).all()
    return templates.TemplateResponse(
        "admin/shop.html",
        _ctx(request, admin, items=items),
    )


@router.post("/shop/new")
async def shop_create(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    code: Annotated[str, Form()],
    title: Annotated[str, Form()],
    item_type: Annotated[str, Form()],
    price_xp: Annotated[int, Form()],
    value: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    db.add(
        ShopItem(
            code=code.strip(),
            title=title.strip(),
            item_type=item_type,
            price_xp=price_xp,
            value=value.strip(),
            description=description.strip() or None,
        )
    )
    db.commit()
    return RedirectResponse("/admin/shop?ok=1", status_code=302)


@router.post("/shop/{item_id}/toggle")
async def shop_toggle(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    item = db.get(ShopItem, item_id)
    if item:
        item.is_active = not item.is_active
        db.commit()
    return RedirectResponse("/admin/shop", status_code=302)


# ——— Статистика и экспорт ———


@router.get("/stats", response_class=HTMLResponse)
async def stats(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    students = db.query(User).filter(User.role == UserRole.STUDENT).all()
    topics = db.query(Topic).filter(Topic.parent_id.isnot(None)).all()
    topic_stats = []
    for t in topics:
        progs = db.query(UserTopicProgress).filter(UserTopicProgress.topic_id == t.id).all()
        avg = sum(p.progress for p in progs) / len(progs) if progs else 0
        topic_stats.append({"topic": t, "avg": avg, "n": len(progs)})
    return templates.TemplateResponse(
        "admin/stats.html",
        _ctx(request, admin, students=students, topic_stats=topic_stats, level_title=level_title),
    )


@router.get("/export/students")
async def export_students(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    data = export_students_csv(db)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=students.csv"},
    )


@router.get("/export/homework")
async def export_hw(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    data = export_homework_csv(db)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=homework.csv"},
    )


@router.get("/calendar", response_class=HTMLResponse)
async def calendar(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    filter: str = "upcoming",
):
    lessons = (
        db.query(Lesson)
        .filter(Lesson.scheduled_at.isnot(None))
        .order_by(Lesson.scheduled_at.asc())
        .all()
    )
    now = datetime.utcnow()
    if filter == "upcoming":
        lessons = [l for l in lessons if l.scheduled_at and l.scheduled_at >= now]
    elif filter == "past":
        lessons = [l for l in lessons if l.scheduled_at and l.scheduled_at < now]
        lessons = list(reversed(lessons))
    # Группировка по дате
    groups: dict[str, list] = {}
    for l in lessons:
        if not l.scheduled_at:
            continue
        key = l.scheduled_at.strftime("%Y-%m-%d")
        groups.setdefault(key, []).append(l)
    return templates.TemplateResponse(
        "admin/calendar.html",
        _ctx(request, admin, lessons=lessons, groups=groups, filter=filter),
    )


@router.get("/templates", response_class=HTMLResponse)
async def lesson_templates(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    items = db.query(LessonTemplate).order_by(LessonTemplate.title).all()
    return templates.TemplateResponse(
        "admin/templates.html",
        _ctx(request, admin, items=items),
    )


@router.post("/templates/new")
async def template_create(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    content: Annotated[str, Form()] = "",
    subject: Annotated[str, Form()] = "math",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    db.add(
        LessonTemplate(
            title=title.strip(),
            description=description.strip() or None,
            content=content.strip() or None,
            subject=subject,
            created_by=admin.id,
        )
    )
    db.commit()
    return RedirectResponse("/admin/templates?ok=1", status_code=302)
