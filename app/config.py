import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Supabase
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.environ.get("SUPABASE_JWT_SECRET", "")

    # ── Integrasi API Eksternal Kelompok UMKM (REQ-INTEG-001) ────────────
    UMKM_API_BASE_URL: str = os.environ.get("UMKM_API_BASE_URL", "")
    UMKM_API_URL: str = os.environ.get("UMKM_API_URL", "")       # deprecated, backward compat
    UMKM_API_KEY: str = os.environ.get("UMKM_API_KEY", "")

    # ── Admin Secret Key (service-to-service ke UMKM Backend) ────────────
    # Harus sama dengan ADMIN_SECRET_KEY di umkm-serverside.
    # Dikirim via header X-Admin-Key ke /api/admin/* UMKM Backend.
    UMKM_ADMIN_SECRET_KEY: str = os.environ.get("UMKM_ADMIN_SECRET_KEY", "")

    # ── Member Lookup API Key (NEW) ───────────────────────────────────────
    # Shared secret antara Gate Backend dan UMKM (frontend/backend).
    # Digunakan oleh UMKM untuk memanggil GET /api/members/lookup.
    # Harus sama dengan GATE_LOOKUP_KEY di UMKM Backend/Frontend .env.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    # Set di HuggingFace Spaces: Settings → Repository secrets → MEMBER_LOOKUP_API_KEY
    MEMBER_LOOKUP_API_KEY: str = os.environ.get("MEMBER_LOOKUP_API_KEY", "")

    # Flag mock data integrasi UMKM.
    UMKM_USE_MOCK: bool = os.environ.get("UMKM_USE_MOCK", "true").lower() == "true"

    # App
    DEBUG: bool = os.environ.get("APP_DEBUG", "false").lower() == "true"
    PORT: int = int(os.environ.get("PORT", 8000))


config = Config()