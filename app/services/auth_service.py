"""
services/auth_service.py
─────────────────────────
Business logic untuk autentikasi dan manajemen profil admin.
"""

import logging

import httpx
from fastapi import HTTPException, status
from gotrue.errors import AuthApiError

from app.core.config import settings
from app.db.client import get_supabase

logger = logging.getLogger(__name__)


def login(email: str, password: str) -> dict:
    """Autentikasi via Supabase Auth, kembalikan token + profil admin."""
    supabase = get_supabase()

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Field email dan password wajib diisi"},
        )

    try:
        auth_res = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthApiError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Email atau password salah"},
        )
    except Exception:
        logger.exception("Unexpected error during sign_in")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )

    if not auth_res.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Email atau password salah"},
        )

    try:
        admin_res = (
            supabase.table("admin")
            .select("id, nama, email, role")
            .eq("id", auth_res.user.id)
            .single()
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
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


def get_admin_row(user_id: str) -> dict:
    """Ambil row admin dari DB. Raise 404 jika tidak ada."""
    supabase = get_supabase()
    res = (
        supabase.table("admin")
        .select("id, nama, email, role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not res or res.data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": "Profil tidak ditemukan"},
        )
    return res.data


def update_nama(user_id: str, nama: str) -> dict:
    """Update nama tampilan admin."""
    supabase = get_supabase()
    try:
        supabase.table("admin").update({"nama": nama}).eq("id", user_id).execute()
        res = (
            supabase.table("admin")
            .select("id, nama, email, role")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if not res or res.data is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": "Gagal memperbarui nama"},
            )
        return {"status": "success", "message": "Nama berhasil diperbarui", "data": res.data}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error updating nama for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def update_password(user_id: str, password_lama: str, password_baru: str) -> dict:
    """Ganti password: verifikasi lama → update via user JWT."""
    supabase = get_supabase()

    if len(password_baru) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Password baru minimal 8 karakter"},
        )
    if password_baru == password_lama:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Password baru tidak boleh sama dengan password lama"},
        )

    admin_data = get_admin_row(user_id)
    email = admin_data["email"]

    try:
        verify = supabase.auth.sign_in_with_password(
            {"email": email, "password": password_lama}
        )
        if not verify.user or not verify.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Password lama tidak sesuai"},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "Password lama tidak sesuai"},
        )

    try:
        resp = httpx.put(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {verify.session.access_token}",
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type": "application/json",
            },
            json={"password": password_baru},
            timeout=10.0,
        )
        if not resp.is_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": "Gagal mengubah password. Coba lagi beberapa saat."},
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error calling Supabase auth/v1/user for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Gagal menghubungi server autentikasi"},
        )

    return {"status": "success", "message": "Password berhasil diubah"}
