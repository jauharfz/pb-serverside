"""
core/config.py
──────────────
Konfigurasi aplikasi menggunakan pydantic-settings.
Env vars dibaca otomatis dari .env (atau environment OS).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # ── Integrasi UMKM ────────────────────────────────────────────────────────
    UMKM_API_BASE_URL: str = ""
    UMKM_API_URL: str = ""          # deprecated, backward compat
    UMKM_API_KEY: str = ""
    UMKM_ADMIN_SECRET_KEY: str = ""
    UMKM_USE_MOCK: bool = True

    # ── Member Lookup ─────────────────────────────────────────────────────────
    MEMBER_LOOKUP_API_KEY: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    APP_DEBUG: bool = False
    PORT: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


# Convenience alias — gunakan `from app.core.config import settings`
settings: Settings = get_settings()
