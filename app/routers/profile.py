"""
Router: Profil & Pengaturan Akun Admin
────────────────────────────────────────
GET  /api/auth/me       → ambil data profil sendiri
PUT  /api/auth/profile  → update nama
PUT  /api/auth/password → ganti password (verifikasi password lama dulu)

Semua endpoint butuh token Bearer (require_auth).
Hanya menyentuh row milik user yang sedang login (current_user.user_id).

━━━ CHANGELOG FIXES ━━━
[BUG FIX 1] PUT /api/auth/profile — 500 AttributeError
  supabase-py v2: .update().eq() menghasilkan SyncFilterRequestBuilder
  yang TIDAK punya method .select(). Chain update+select tidak didukung.
  Fix: split menjadi dua operasi terpisah — update dulu, lalu re-fetch.

[BUG FIX 2] PUT /api/auth/password — 500 / 403 Forbidden
  supabase.auth.admin.update_user_by_id() membutuhkan service_role key.
  Jika SUPABASE_SERVICE_ROLE_KEY berisi anon key, Supabase menolak dengan
  403 Forbidden.
  Fix: Gunakan access_token user sendiri (dari hasil verify sign_in) untuk
  memanggil PUT /auth/v1/user langsung via httpx. Endpoint ini hanya butuh
  user's own JWT sebagai Bearer — tidak perlu service_role key sama sekali.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import config
from app.dependencies import CurrentUser, require_auth, supabase

router = APIRouter(tags=["Profil Admin"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class UpdateNamaBody(BaseModel):
    nama: str


class UpdatePasswordBody(BaseModel):
    password_lama: str
    password_baru: str


# ── Helper internal ───────────────────────────────────────────────────────────

def _get_admin_row(user_id: str) -> dict:
    """Ambil row admin dari DB. Raise 404 jika tidak ada."""
    res = (
        supabase.table("admin")
        .select("id, nama, email, role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not res or res.data is None:
        raise HTTPException(
            status_code=404,
            detail={"status": "error", "message": "Profil tidak ditemukan"},
        )
    return res.data


# ── GET /api/auth/me ──────────────────────────────────────────────────────────

@router.get("/auth/me")
def get_me(current_user: CurrentUser = Depends(require_auth)):
    """Ambil data profil admin yang sedang login."""
    data = _get_admin_row(current_user.user_id)
    return {"status": "success", "data": data}


# ── PUT /api/auth/profile ─────────────────────────────────────────────────────

@router.put("/auth/profile")
def update_nama(
    body: UpdateNamaBody,
    current_user: CurrentUser = Depends(require_auth),
):
    """
    Update nama tampilan admin yang sedang login.

    FIX: supabase-py v2 tidak mendukung chain .update().eq().select().
    SyncFilterRequestBuilder tidak memiliki method .select().
    Solusi: jalankan .update().eq().execute() terlebih dahulu,
    lalu fetch ulang dengan .select().eq().maybe_single().execute().
    """
    nama = body.nama.strip()
    if not nama:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Nama tidak boleh kosong"},
        )

    try:
        # Step 1: Update nama (tidak chain .select() di sini)
        supabase.table("admin") \
            .update({"nama": nama}) \
            .eq("id", current_user.user_id) \
            .execute()

        # Step 2: Fetch ulang data terbaru
        res = (
            supabase.table("admin")
            .select("id, nama, email, role")
            .eq("id", current_user.user_id)
            .maybe_single()
            .execute()
        )

        if not res or res.data is None:
            raise HTTPException(
                status_code=500,
                detail={"status": "error", "message": "Gagal memperbarui nama"},
            )

        return {
            "status": "success",
            "message": "Nama berhasil diperbarui",
            "data": res.data,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── PUT /api/auth/password ────────────────────────────────────────────────────

@router.put("/auth/password")
def update_password(
    body: UpdatePasswordBody,
    current_user: CurrentUser = Depends(require_auth),
):
    """
    Ganti password admin.
    Alur: verifikasi password lama via sign_in → update via user's own JWT.

    FIX: Endpoint admin.update_user_by_id() membutuhkan service_role key.
    Jika key yang dikonfigurasi adalah anon key, Supabase akan menolak
    dengan 403 Forbidden.
    Solusi: Gunakan access_token dari sesi verifikasi untuk memanggil
    PUT /auth/v1/user secara langsung. Endpoint ini tidak memerlukan
    service_role — cukup user's own Bearer token.
    """
    if len(body.password_baru) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Password baru minimal 8 karakter"},
        )

    if body.password_baru == body.password_lama:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Password baru tidak boleh sama dengan password lama"},
        )

    # Ambil email dari DB — jangan percaya body untuk mencegah spoofing
    admin_data = _get_admin_row(current_user.user_id)
    email = admin_data["email"]

    # Verifikasi password lama — sekaligus dapat access_token segar
    try:
        verify = supabase.auth.sign_in_with_password(
            {"email": email, "password": body.password_lama}
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

    # Update password via PUT /auth/v1/user menggunakan user's own JWT
    # Tidak membutuhkan service_role key — cukup user's Bearer token.
    try:
        user_access_token = verify.session.access_token
        resp = httpx.put(
            f"{config.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {user_access_token}",
                # apikey bisa anon key atau service_role — keduanya diterima
                "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type": "application/json",
            },
            json={"password": body.password_baru},
            timeout=10.0,
        )

        if not resp.is_success:
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": f"Gagal mengubah password. Coba lagi beberapa saat.",
                },
            )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Gagal menghubungi server autentikasi"},
        )

    return {"status": "success", "message": "Password berhasil diubah"}