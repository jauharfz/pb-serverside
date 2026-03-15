import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Supabase
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.environ.get("SUPABASE_JWT_SECRET", "")

    # External UMKM API (kelompok lain)
    UMKM_API_URL: str = os.environ.get("UMKM_API_URL", "")
    UMKM_API_KEY: str = os.environ.get("UMKM_API_KEY", "")

    # Flask
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    PORT: int = int(os.environ.get("PORT", 5000))
