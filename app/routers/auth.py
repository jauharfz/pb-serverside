"""
Router: Autentikasi
────────────────────
POST /api/auth/login  → REQ-AUTH-001
"""

from fastapi import APIRouter
from gotrue.errors import AuthApiError
from pydantic import BaseModel

from app.dependencies import supabase

router = APIRouter(tags=["Auth"])


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: LoginBody):
    email = body.email.strip()
    password = body.password

    if not email or not password:
        return {
            "status": "error",
            "message": "Field email dan password wajib diisi",
        }, 422

    # ── Supabase Auth ─────────────────────────────────────────────────────
    try:
        auth_res = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthApiError:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Email atau password salah"},
        )
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )

    if not auth_res.session:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Email atau password salah"},
        )

    # ── Ambil profil dari tabel admin ─────────────────────────────────────
    try:
        admin_res = (
            supabase.table("admin")
            .select("id, nama, email, role")
            .eq("id", auth_res.user.id)
            .single()
            .execute()
        )
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Akun tidak ditemukan dalam sistem"},
        )

    return {
        "status": "success",
        "message": "Login berhasil",
        "data": {
            "token": auth_res.session.access_token,
            "user": admin_res.data,
        },
    }
