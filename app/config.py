"""Конфигурация приложения Skillik."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки из окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Skillik"
    secret_key: str = "dev-secret-change-in-production-skillik-2024"
    debug: bool = True
    database_url: str = f"sqlite:///{BASE_DIR / 'skillik.db'}"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 дней
    algorithm: str = "HS256"
    upload_dir: Path = BASE_DIR / "app" / "static" / "uploads"
    max_upload_mb: int = 20
    cookie_name: str = "skillik_token"
    csrf_cookie_name: str = "skillik_csrf"

    # Разрешённые расширения загрузок
    allowed_extensions: set[str] = {
        ".pdf",
        ".doc",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".txt",
        ".zip",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
