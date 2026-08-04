"""Точка входа Skillik — FastAPI приложение."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.deps import get_current_user_optional
from app.models.user import User, UserRole
from app.routers import admin, auth, parent, student
from app.security import generate_csrf_token, sign_csrf
from app.services.seed import seed_if_empty

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Образовательная платформа Skillik",
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

# Сессии (для совместимости / доп. данных)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# Статика
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Роутеры
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(student.router)
app.include_router(parent.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """CSRF double-submit + базовые заголовки безопасности."""
    from app.security import verify_csrf

    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    raw = None
    need_set = False
    if cookie and "." in cookie:
        candidate, sig = cookie.rsplit(".", 1)
        if verify_csrf(candidate, sig):
            raw = candidate
    if not raw:
        raw = generate_csrf_token()
        need_set = True
    request.state.csrf_token = raw

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "frame-src https://www.youtube.com https://youtube.com; "
        "connect-src 'self'"
    )
    if need_set:
        response.set_cookie(
            key=settings.csrf_cookie_name,
            value=f"{raw}.{sign_csrf(raw)}",
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24,
            path="/",
        )
    return response


@app.get("/", response_class=HTMLResponse)
async def index(user: User | None = Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.role == UserRole.ADMIN:
        return RedirectResponse("/admin", status_code=302)
    if user.role == UserRole.PARENT:
        return RedirectResponse("/parent", status_code=302)
    return RedirectResponse("/student", status_code=302)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
