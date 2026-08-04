"""Авторизация: вход / выход / смена пароля."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import csrf_token_for, get_current_user, get_current_user_optional, verify_csrf_form
from app.models.user import User, UserRole
from app.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.gamification import record_activity

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _set_auth_cookie(response: Response, user: User) -> None:
    token = create_access_token(user.id, extra={"role": user.role.value})
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Annotated[Optional[User], Depends(get_current_user_optional)],
    error: str | None = None,
):
    if user:
        return RedirectResponse(_home_for(user), status_code=302)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": error, "csrf_token": csrf_token_for(request)},
    )


def _home_for(user: User) -> str:
    if user.role == UserRole.ADMIN:
        return "/admin"
    if user.role == UserRole.PARENT:
        return "/parent"
    return "/student"


@router.post("/login")
async def login_post(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Неверный логин или пароль",
                "csrf_token": csrf_token_for(request),
            },
            status_code=400,
        )
    if user.is_blocked or not user.is_active:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": "Аккаунт заблокирован. Обратитесь к преподавателю.",
                "csrf_token": csrf_token_for(request),
            },
            status_code=403,
        )

    user.last_login = datetime.now(timezone.utc)
    if user.role == UserRole.STUDENT:
        record_activity(db, user)
    db.commit()

    resp = RedirectResponse(_home_for(user), status_code=status.HTTP_302_FOUND)
    _set_auth_cookie(resp, user)
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(settings.cookie_name, path="/")
    return resp


@router.get("/parent/login", response_class=HTMLResponse)
async def parent_login_page(request: Request):
    return templates.TemplateResponse(
        "auth/parent_login.html",
        {"request": request, "error": None, "csrf_token": csrf_token_for(request)},
    )


@router.post("/parent/login")
async def parent_login_post(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    user = db.query(User).filter(User.username == username.strip()).first()
    if (
        not user
        or user.role != UserRole.PARENT
        or not verify_password(password, user.password_hash)
        or user.is_blocked
    ):
        return templates.TemplateResponse(
            "auth/parent_login.html",
            {
                "request": request,
                "error": "Неверный логин или пароль родителя",
                "csrf_token": csrf_token_for(request),
            },
            status_code=400,
        )

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    resp = RedirectResponse("/parent", status_code=302)
    _set_auth_cookie(resp, user)
    return resp


@router.post("/profile/password")
async def change_password(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    _: Annotated[None, Depends(verify_csrf_form)] = None,
):
    if not verify_password(current_password, user.password_hash):
        return RedirectResponse("/student/profile?error=bad_password", status_code=302)
    if len(new_password) < 6:
        return RedirectResponse("/student/profile?error=short", status_code=302)
    user.password_hash = hash_password(new_password)
    db.commit()
    target = "/admin" if user.is_admin else ("/parent" if user.is_parent else "/student/profile")
    return RedirectResponse(f"{target}?ok=password", status_code=302)
