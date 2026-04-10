"""
db/client.py
────────────
Supabase service-role client (singleton).
Service-role client: bypasses RLS, dipakai untuk semua operasi server-side.
Keamanan akses dikendalikan penuh oleh dependency auth (JWT + role check).
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    """Mengembalikan Supabase client singleton (lazy + cached)."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY harus diisi di .env"
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
