import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Supabase
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.environ.get("SUPABASE_JWT_SECRET", "")

    # ── Integrasi API Eksternal Kelompok UMKM (REQ-INTEG-001) ────────────
    # Base URL API UMKM: misal https://jauharfz-umkm-serverside.hf.space
    # Endpoint public/tenant dan public/diskon akan di-append otomatis.
    UMKM_API_BASE_URL: str = os.environ.get("UMKM_API_BASE_URL", "")

    # Deprecated — hanya untuk backward compat. Gunakan UMKM_API_BASE_URL.
    UMKM_API_URL: str = os.environ.get("UMKM_API_URL", "")
    UMKM_API_KEY: str = os.environ.get("UMKM_API_KEY", "")

    # Flag mock data integrasi UMKM.
    # true  → kembalikan data dummy hardcode (untuk dev/testing).
    # false → panggil API UMKM sungguhan via UMKM_API_BASE_URL.
    UMKM_USE_MOCK: bool = os.environ.get("UMKM_USE_MOCK", "true").lower() == "true"

    # App
    DEBUG: bool = os.environ.get("APP_DEBUG", "false").lower() == "true"
    PORT: int = int(os.environ.get("PORT", 8000))


config = Config()