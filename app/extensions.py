from supabase import create_client, Client
from app.config import Config

# Service-role client: bypasses RLS, dipakai untuk semua operasi server-side.
# Keamanan akses dikendalikan penuh oleh Flask middleware (JWT + role check).
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_ROLE_KEY)
