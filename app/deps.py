"""Зависимости FastAPI: текущий пользователь, роли, CSRF."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Form, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole
from app.security import decode_access_token, verify_csrf

settings = get_settings()


def get_token_from_request(request: Request) -> Optional[str]:
    """JWT из cookie или Authorization Bearer."""
    token = request.cookies.get(settings.cookie_name)
    if token:
        return token
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_current_user_optional(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Optional[User]:
    """Текущий пользователь или None."""
    token = get_token_from_request(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active or user.is_blocked:
        return None
    return user


def get_current_user(
    user: Annotated[Optional[User], Depends(get_current_user_optional)],
) -> User:
    """Обязательная авторизация."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется вход",
        )
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Только для администратора")
    return user


def require_student(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Только для ученика")
    return user


def require_parent(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.PARENT:
        raise HTTPException(status_code=403, detail="Только для родителя")
    return user


def verify_csrf_form(
    request: Request,
    csrf_token: Annotated[str, Form(alias="csrf_token")] = "",
) -> None:
    """Проверка CSRF для POST-форм."""
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    # cookie = token.signature
    if not cookie_token or "." not in cookie_token:
        raise HTTPException(status_code=403, detail="Недействительный CSRF")
    raw, sig = cookie_token.rsplit(".", 1)
    if not verify_csrf(raw, sig) or raw != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF-токен не совпадает")


def set_csrf_cookie(response, token: str, signature: str) -> None:
    from app.config import get_settings as gs

    s = gs()
    response.set_cookie(
        key=s.csrf_cookie_name,
        value=f"{token}.{signature}",
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
        path="/",
    )


def csrf_token_for(request: Request) -> str:
    """Токен CSRF из request.state (middleware) или cookie."""
    token = getattr(request.state, "csrf_token", None)
    if token:
        return token
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    if cookie and "." in cookie:
        raw, sig = cookie.rsplit(".", 1)
        if verify_csrf(raw, sig):
            return raw
    from app.security import generate_csrf_token

    return generate_csrf_token()
