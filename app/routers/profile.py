"""
Router: Profil & Pengaturan Akun Admin
────────────────────────────────────────
GET  /api/auth/me       → ambil data profil sendiri
PUT  /api/auth/profile  → update nama
PUT  /api/auth/password → ganti password (verifikasi password lama dulu)

Semua endpoint butuh token Bearer (require_auth).
Hanya menyentuh row milik user yang sedang login (current_user.user_id).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

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
    """Update nama tampilan admin yang sedang login."""
    nama = body.nama.strip()
    if not nama:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Nama tidak boleh kosong"},
        )

    res = (
        supabase.table("admin")
        .update({"nama": nama})
        .eq("id", current_user.user_id)
        .select("id, nama, email, role")
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


# ── PUT /api/auth/password ────────────────────────────────────────────────────

@router.put("/auth/password")
def update_password(
    body: UpdatePasswordBody,
    current_user: CurrentUser = Depends(require_auth),
):
    """
    Ganti password admin.
    Alur: verifikasi password lama via sign_in → update via admin API.
    Email diambil dari tabel admin (bukan dari body) untuk mencegah spoofing.
    """
    if len(body.password_baru) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Password baru minimal 8 karakter"},
        )

    # Ambil email dari DB — jangan percaya body
    admin_data = _get_admin_row(current_user.user_id)
    email = admin_data["email"]

    # Verifikasi password lama
    try:
        verify = supabase.auth.sign_in_with_password(
            {"email": email, "password": body.password_lama}
        )
        if not verify.user:
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

    # Update password via Supabase Admin API
    try:
        supabase.auth.admin.update_user_by_id(
            current_user.user_id,
            {"password": body.password_baru},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": f"Gagal mengubah password: {str(e)}"},
        )

    return {"status": "success", "message": "Password berhasil diubah"}