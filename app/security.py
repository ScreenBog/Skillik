"""Безопасность: пароли, JWT, CSRF."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# bcrypt для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Хэш пароля (bcrypt)."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Проверка пароля."""
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(
    subject: str | int,
    extra: Optional[dict[str, Any]] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    """Создать JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire, "iat": datetime.now(timezone.utc)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Декодировать JWT; None при ошибке."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None


def generate_csrf_token() -> str:
    """Случайный CSRF-токен."""
    return secrets.token_urlsafe(32)


def sign_csrf(token: str) -> str:
    """Подпись CSRF-токена (HMAC)."""
    return hmac.new(
        settings.secret_key.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_csrf(token: str, signature: str) -> bool:
    """Проверка CSRF-подписи."""
    expected = sign_csrf(token)
    return hmac.compare_digest(expected, signature)


def sanitize_filename(name: str) -> str:
    """Безопасное имя файла (защита от path traversal)."""
    import re
    from pathlib import Path

    base = Path(name).name
    base = re.sub(r"[^\w.\-а-яА-ЯёЁ ]+", "_", base, flags=re.UNICODE)
    return base[:200] or "file"
