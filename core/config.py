from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    bot_token: str = ""
    webapp_url: str = ""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_webapp_configured(settings: Settings) -> bool:
    """
    Проверяем, что в .env указан реальный веб-адрес Mini App.

    Telegram Mini App должен открываться по HTTPS.
    Поэтому локальные http:// адреса пока считаем не готовыми.
    """
    url = settings.webapp_url.strip().lower()

    if not url:
        return False

    if url == "https://your-domain.example.com":
        return False

    if url.startswith("http://"):
        return False

    return True