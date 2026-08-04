"""Личный кабинет ученика."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import require_student, verify_csrf_form
from app.models.achievement import Achievement, UserAchievement
from app.models.extras import Announcement, HelpRequest, StudentNote
from app.models.feedback import LessonFeedback
from app.models.homework import Homework, HomeworkStatus, HomeworkSubmission
from app.models.lesson import Lesson
from app.models.message import Message, UrgentQuestion
from app.models.shop import ShopItem, UserPurchase
from app.models.topic import Topic, UserTopicProgress
from app.models.user import User, UserRole
from app.deps import csrf_token_for
from app.security import sanitize_filename
from app.services.daily_challenge import pick_daily_challenge
from app.services.gamification import (
    add_xp,
    freeze_streak,
    level_for_xp,
    next_level_info,
    record_activity,
)
from app.services.homework_check import check_answers, tasks_to_public
from app.templating import get_templates

router = APIRouter(prefix="/student", tags=["student"])
templates = get_templates()
settings = get_settings()


def _ctx(request: Request, user: User, **kwargs):
    return {
        "request": request,
        "user": user,
        "csrf_token": csrf_token_for(request),
        "app_name": settings.app_name,
        "level_info": next_level_info(user.xp),
        **kwargs,
    }


def _admin(db: Session) -> Optional[User]:
    return db.query(User).filter(User.role == UserRole.ADMIN).first()


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    record_activity(db, student)
    db.commit()

    from app.models.xp import Streak

    streak = db.query(Streak).filter(Streak.user_id == student.id).first()
    next_lesson = (
        db.query(Lesson)
        .filter(
            Lesson.is_published.is_(True),
            Lesson.scheduled_at.isnot(None),
            Lesson.scheduled_at >= datetime.now(timezone.utc).replace(tzinfo=None),
            (Lesson.student_id.is_(None)) | (Lesson.student_id == student.id),
        )
        .order_by(Lesson.scheduled_at.asc())
        .first()
    )
    pending_hw = (
        db.query(Homework)
        .filter(
            Homework.student_id == student.id,
            Homework.status.in_(
                [HomeworkStatus.ASSIGNED, HomeworkStatus.IN_PROGRESS, HomeworkStatus.DEFERRED]
            ),
        )
        .order_by(Homework.due_at.asc().nullslast())
        .limit(5)
        .all()
    )
    new_lessons = (
        db.query(Lesson)
        .filter(
            Lesson.is_published.is_(True),
            (Lesson.student_id.is_(None)) | (Lesson.student_id == student.id),
        )
        .order_by(Lesson.created_at.desc())
        .limit(5)
        .all()
    )
    # Задача дня — первое незакрытое ДЗ
    daily = pending_hw[0] if pending_hw else None
    challenge = pick_daily_challenge(db, student.id)
    announcements = (
        db.query(Announcement)
        .filter(
            Announcement.is_active.is_(True),
            Announcement.audience.in_(["all", "students"]),
        )
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(5)
        .all()
    )
    recent_ach = (
        db.query(UserAchievement)
        .filter(UserAchievement.user_id == student.id)
        .order_by(UserAchievement.earned_at.desc())
        .limit(3)
        .all()
    )
    my_help = (
        db.query(HelpRequest)
        .filter(HelpRequest.student_id == student.id, HelpRequest.status == "open")
        .count()
    )
    return templates.TemplateResponse(
        "student/dashboard.html",
        _ctx(
            request,
            student,
            streak=streak,
            next_lesson=next_lesson,
            pending_hw=pending_hw,
            new_lessons=new_lessons,
            daily=daily,
            challenge=challenge,
            announcements=announcements,
            recent_ach=recent_ach,
            my_help=my_help,
        ),
    )


@router.get("/lessons", response_class=HTMLResponse)
async def lessons(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    items = (
        db.query(Lesson)
        .filter(
            Lesson.is_published.is_(True),
            (Lesson.student_id.is_(None)) | (Lesson.student_id == student.id),
        )
        .order_by(Lesson.scheduled_at.desc().nullslast())
        .all()
    )
    return templates.TemplateResponse(
        "student/lessons.html",
        _ctx(request, student, lessons=items),
    )


@router.get("/lessons/{lesson_id}", response_class=HTMLResponse)
async def lesson_view(
    lesson_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson or not lesson.is_published:
        return RedirectResponse("/student/lessons", status_code=302)
    if lesson.student_id and lesson.student_id != student.id:
        return RedirectResponse("/student/lessons", status_code=302)
    fb = (
        db.query(LessonFeedback)
        .filter(
            LessonFeedback.lesson_id == lesson_id,
            LessonFeedback.student_id == student.id,
        )
        .first()
    )
    return templates.TemplateResponse(
        "student/lesson_detail.html",
        _ctx(request, student, lesson=lesson, feedback=fb),
    )


@router.post("/lessons/{lesson_id}/feedback")
async def lesson_feedback(
    lesson_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    difficulty: Annotated[str, Form()],
    comment: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    if difficulty not in ("hard", "normal", "easy"):
        return RedirectResponse(f"/student/lessons/{lesson_id}", status_code=302)
    exists = (
        db.query(LessonFeedback)
        .filter(
            LessonFeedback.lesson_id == lesson_id,
            LessonFeedback.student_id == student.id,
        )
        .first()
    )
    if not exists:
        db.add(
            LessonFeedback(
                lesson_id=lesson_id,
                student_id=student.id,
                difficulty=difficulty,
                comment=comment.strip() or None,
            )
        )
        add_xp(db, student, 5, "lesson_feedback", f"lesson {lesson_id}")
        db.commit()
    return RedirectResponse(f"/student/lessons/{lesson_id}?ok=fb", status_code=302)


@router.get("/homework", response_class=HTMLResponse)
async def homework_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    items = (
        db.query(Homework)
        .filter(Homework.student_id == student.id)
        .order_by(Homework.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "student/homework.html",
        _ctx(request, student, items=items),
    )


@router.get("/homework/{hw_id}", response_class=HTMLResponse)
async def homework_view(
    hw_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    hw = db.get(Homework, hw_id)
    if not hw or hw.student_id != student.id:
        return RedirectResponse("/student/homework", status_code=302)
    tasks = tasks_to_public(hw.auto_check_json)
    help_req = (
        db.query(HelpRequest)
        .filter(
            HelpRequest.homework_id == hw_id,
            HelpRequest.student_id == student.id,
        )
        .order_by(HelpRequest.created_at.desc())
        .first()
    )
    return templates.TemplateResponse(
        "student/homework_detail.html",
        _ctx(request, student, hw=hw, tasks=tasks, help_req=help_req),
    )


@router.post("/homework/{hw_id}/help")
async def homework_help(
    hw_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    message: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    hw = db.get(Homework, hw_id)
    if not hw or hw.student_id != student.id:
        return RedirectResponse("/student/homework", status_code=302)
    if not message.strip():
        return RedirectResponse(f"/student/homework/{hw_id}?error=empty", status_code=302)
    open_one = (
        db.query(HelpRequest)
        .filter(
            HelpRequest.homework_id == hw_id,
            HelpRequest.student_id == student.id,
            HelpRequest.status == "open",
        )
        .first()
    )
    if open_one:
        open_one.message = message.strip()
    else:
        db.add(
            HelpRequest(
                homework_id=hw_id,
                student_id=student.id,
                message=message.strip(),
            )
        )
    db.commit()
    return RedirectResponse(f"/student/homework/{hw_id}?ok=help", status_code=302)


@router.post("/homework/{hw_id}/submit")
async def homework_submit(
    hw_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    text_answer: Annotated[str, Form()] = "",
    file: Annotated[Optional[UploadFile], File()] = None,
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    hw = db.get(Homework, hw_id)
    if not hw or hw.student_id != student.id:
        return RedirectResponse("/student/homework", status_code=302)
    if hw.status == HomeworkStatus.GRADED:
        return RedirectResponse(f"/student/homework/{hw_id}", status_code=302)

    form = await request.form()
    answers: dict[str, str] = {}
    for k, v in form.items():
        if k.startswith("q_"):
            answers[k[2:]] = str(v)

    auto_score = None
    auto_json = None
    if hw.auto_check_json:
        got, total, details = check_answers(hw.auto_check_json, answers)
        auto_json = json.dumps(details, ensure_ascii=False)
        if total > 0:
            auto_score = round(got / total * hw.max_score, 2)

    file_path = None
    original = None
    if file and file.filename:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        dest = settings.upload_dir / "submissions"
        dest.mkdir(exist_ok=True)
        original = sanitize_filename(file.filename)
        ext = Path(original).suffix.lower()
        if ext in settings.allowed_extensions:
            stored = f"{secrets.token_hex(8)}_{original}"
            content = await file.read()
            if len(content) <= settings.max_upload_mb * 1024 * 1024:
                (dest / stored).write_bytes(content)
                file_path = f"submissions/{stored}"

    sub = hw.submission
    if not sub:
        sub = HomeworkSubmission(homework_id=hw.id, student_id=student.id)
        db.add(sub)
    sub.text_answer = text_answer.strip() or None
    sub.auto_answers_json = auto_json
    sub.auto_score = auto_score
    if file_path:
        sub.file_path = file_path
        sub.original_filename = original
    sub.submitted_at = datetime.utcnow()
    hw.status = HomeworkStatus.SUBMITTED

    # Автооценка при полной автопроверке
    if auto_score is not None and hw.auto_check_json and not text_answer.strip() and not file_path:
        sub.score = auto_score
        sub.graded_at = datetime.utcnow()
        hw.status = HomeworkStatus.GRADED
        add_xp(db, student, hw.xp_reward, "homework_auto", f"ДЗ #{hw.id}")

    record_activity(db, student)
    db.commit()
    return RedirectResponse(f"/student/homework/{hw_id}?ok=submitted", status_code=302)


@router.post("/homework/{hw_id}/defer")
async def homework_defer(
    hw_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    """Использовать покупку отсрочки +1 день."""
    hw = db.get(Homework, hw_id)
    if not hw or hw.student_id != student.id or not hw.due_at:
        return RedirectResponse("/student/homework", status_code=302)
    purchase = (
        db.query(UserPurchase)
        .join(ShopItem)
        .filter(
            UserPurchase.user_id == student.id,
            UserPurchase.is_used.is_(False),
            ShopItem.item_type == "defer_hw",
        )
        .first()
    )
    if not purchase:
        return RedirectResponse(f"/student/homework/{hw_id}?error=no_defer", status_code=302)
    from datetime import timedelta

    hw.due_at = hw.due_at + timedelta(days=1)
    hw.status = HomeworkStatus.DEFERRED
    purchase.is_used = True
    db.commit()
    return RedirectResponse(f"/student/homework/{hw_id}?ok=defer", status_code=302)


@router.get("/map", response_class=HTMLResponse)
async def knowledge_map(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    roots = db.query(Topic).filter(Topic.parent_id.is_(None), Topic.is_active.is_(True)).order_by(Topic.order_index).all()
    progress = {
        p.topic_id: p
        for p in db.query(UserTopicProgress).filter(UserTopicProgress.user_id == student.id).all()
    }
    return templates.TemplateResponse(
        "student/map.html",
        _ctx(request, student, roots=roots, progress=progress),
    )


@router.get("/practice", response_class=HTMLResponse)
async def practice(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    topic_id: int = 0,
):
    topics = db.query(Topic).filter(Topic.parent_id.isnot(None), Topic.is_active.is_(True)).all()
    topic = db.get(Topic, topic_id) if topic_id else None
    # Простые тренировочные вопросы (встроенные + из ДЗ с автопроверкой)
    tasks = []
    if topic:
        hws = (
            db.query(Homework)
            .filter(
                Homework.topic_id == topic.id,
                Homework.auto_check_json.isnot(None),
            )
            .limit(5)
            .all()
        )
        for h in hws:
            tasks.extend(tasks_to_public(h.auto_check_json))
        if not tasks:
            # Демо-задания по теме
            tasks = [
                {
                    "id": "demo1",
                    "type": "input",
                    "question": f"Тренировка: вспомни ключевую идею темы «{topic.title}». Напиши одно слово-ассоциацию.",
                    "points": 1,
                }
            ]
    return templates.TemplateResponse(
        "student/practice.html",
        _ctx(request, student, topics=topics, topic=topic, tasks=tasks),
    )


@router.post("/practice")
async def practice_submit(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    topic_id: Annotated[int, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    """Завершение тренировки — +XP и прогресс темы."""
    topic = db.get(Topic, topic_id)
    if topic:
        prog = (
            db.query(UserTopicProgress)
            .filter(
                UserTopicProgress.user_id == student.id,
                UserTopicProgress.topic_id == topic_id,
            )
            .first()
        )
        if not prog:
            prog = UserTopicProgress(user_id=student.id, topic_id=topic_id)
            db.add(prog)
        prog.progress = min(100.0, prog.progress + 5)
        prog.mastery = "learning" if prog.progress < 40 else ("practiced" if prog.progress < 80 else "mastered")
        prog.last_practiced = datetime.utcnow()
        add_xp(db, student, 10, "practice", topic.slug)
        record_activity(db, student)
        db.commit()
    return RedirectResponse(f"/student/practice?topic_id={topic_id}&ok=practice", status_code=302)


@router.get("/achievements", response_class=HTMLResponse)
async def achievements(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    all_a = db.query(Achievement).filter(Achievement.is_active.is_(True)).all()
    earned = {
        ua.achievement_id: ua
        for ua in db.query(UserAchievement).filter(UserAchievement.user_id == student.id).all()
    }
    return templates.TemplateResponse(
        "student/achievements.html",
        _ctx(request, student, all_a=all_a, earned=earned),
    )


@router.get("/shop", response_class=HTMLResponse)
async def shop(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    msg: str = "",
):
    items = (
        db.query(ShopItem)
        .filter(ShopItem.is_active.is_(True))
        .order_by(ShopItem.sort_order)
        .all()
    )
    purchases = (
        db.query(UserPurchase)
        .filter(UserPurchase.user_id == student.id)
        .order_by(UserPurchase.purchased_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        "student/shop.html",
        _ctx(request, student, items=items, purchases=purchases, msg=msg),
    )


@router.post("/shop/{item_id}/buy")
async def shop_buy(
    item_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    item = db.get(ShopItem, item_id)
    if not item or not item.is_active:
        return RedirectResponse("/student/shop?msg=error", status_code=302)
    if student.xp < item.price_xp:
        return RedirectResponse("/student/shop?msg=nomoney", status_code=302)
    add_xp(db, student, -item.price_xp, "shop_buy", item.code)
    purchase = UserPurchase(user_id=student.id, item_id=item.id, price_paid=item.price_xp)
    db.add(purchase)

    # Применить сразу для косметики
    if item.item_type == "avatar":
        student.avatar = item.value
        purchase.is_used = True
    elif item.item_type == "frame":
        student.avatar_frame = item.value
        purchase.is_used = True
    elif item.item_type == "accent_color":
        student.accent_color = item.value
        purchase.is_used = True
    # defer_hw и sticker — is_used=False до применения

    db.commit()
    return RedirectResponse("/student/shop?msg=ok", status_code=302)


@router.get("/messages", response_class=HTMLResponse)
async def messages(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    admin = _admin(db)
    thread: list[Message] = []
    if admin:
        thread = (
            db.query(Message)
            .filter(
                ((Message.sender_id == student.id) & (Message.recipient_id == admin.id))
                | ((Message.sender_id == admin.id) & (Message.recipient_id == student.id))
            )
            .order_by(Message.created_at.asc())
            .all()
        )
        for m in thread:
            if m.recipient_id == student.id and not m.is_read:
                m.is_read = True
        db.commit()
    urgents = (
        db.query(UrgentQuestion)
        .filter(UrgentQuestion.student_id == student.id)
        .order_by(UrgentQuestion.created_at.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse(
        "student/messages.html",
        _ctx(request, student, thread=thread, admin=admin, urgents=urgents),
    )


@router.post("/messages/send")
async def messages_send(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    body: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    admin = _admin(db)
    if admin and body.strip():
        db.add(Message(sender_id=student.id, recipient_id=admin.id, body=body.strip()))
        db.commit()
    return RedirectResponse("/student/messages", status_code=302)


@router.post("/urgent")
async def urgent(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    body: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    if body.strip():
        db.add(UrgentQuestion(student_id=student.id, body=body.strip()))
        db.commit()
    return RedirectResponse("/student/messages?ok=urgent", status_code=302)


@router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    error: str = "",
    ok: str = "",
):
    from app.models.xp import Streak

    streak = db.query(Streak).filter(Streak.user_id == student.id).first()
    return templates.TemplateResponse(
        "student/profile.html",
        _ctx(request, student, streak=streak, error=error, ok=ok, level_key=level_for_xp(student.xp)),
    )


@router.post("/profile")
async def profile_update(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    theme_preference: Annotated[str, Form()] = "system",
    avatar: Annotated[str, Form()] = "default",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    if theme_preference in ("light", "dark", "system"):
        student.theme_preference = theme_preference
    student.avatar = avatar.strip() or "default"
    db.commit()
    return RedirectResponse("/student/profile?ok=1", status_code=302)


@router.post("/streak/freeze")
async def streak_freeze(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    freeze_streak(db, student)
    db.commit()
    return RedirectResponse("/student/profile?ok=freeze", status_code=302)


# ——— Блокнот ———


@router.get("/notes", response_class=HTMLResponse)
async def notes_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
):
    notes = (
        db.query(StudentNote)
        .filter(StudentNote.user_id == student.id)
        .order_by(StudentNote.updated_at.desc())
        .all()
    )
    topics = db.query(Topic).filter(Topic.parent_id.isnot(None)).order_by(Topic.title).all()
    return templates.TemplateResponse(
        "student/notes.html",
        _ctx(request, student, notes=notes, topics=topics),
    )


@router.post("/notes/new")
async def notes_create(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    title: Annotated[str, Form()],
    body: Annotated[str, Form()] = "",
    topic_id: Annotated[str, Form()] = "",
    color: Annotated[str, Form()] = "default",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    if color not in ("default", "yellow", "green", "blue"):
        color = "default"
    if not title.strip():
        return RedirectResponse("/student/notes?error=empty", status_code=302)
    db.add(
        StudentNote(
            user_id=student.id,
            title=title.strip(),
            body=body.strip(),
            topic_id=int(topic_id) if topic_id.isdigit() else None,
            color=color,
        )
    )
    db.commit()
    return RedirectResponse("/student/notes?ok=1", status_code=302)


@router.post("/notes/{note_id}/delete")
async def notes_delete(
    note_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    note = db.get(StudentNote, note_id)
    if note and note.user_id == student.id:
        db.delete(note)
        db.commit()
    return RedirectResponse("/student/notes?ok=1", status_code=302)


@router.post("/notes/{note_id}/edit")
async def notes_edit(
    note_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    title: Annotated[str, Form()],
    body: Annotated[str, Form()] = "",
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    note = db.get(StudentNote, note_id)
    if note and note.user_id == student.id and title.strip():
        note.title = title.strip()
        note.body = body.strip()
        db.commit()
    return RedirectResponse("/student/notes?ok=1", status_code=302)
