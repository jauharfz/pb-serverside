# backend-app/app/routers/profile.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.deps import get_current_admin  # sudah ada di codebase kamu
from app.database import supabase       # supabase client (service_role)
import os

router = APIRouter(prefix="/profile", tags=["Profile"])

# ── Schema ────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    nama: str

class PasswordUpdate(BaseModel):
    password_lama: str
    password_baru: str

class ProfileResponse(BaseModel):
    id: str
    nama: str
    email: str
    role: str


# ── GET /api/profile ──────────────────────────────────────────────
@router.get("", response_model=ProfileResponse)
async def get_profile(current_admin=Depends(get_current_admin)):
    """Ambil data profile admin yang sedang login."""
    result = (
        supabase.table("admin")
        .select("id, nama, email, role")
        .eq("id", current_admin["id"])
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Profile tidak ditemukan")
    return result.data


# ── PUT /api/profile ──────────────────────────────────────────────
@router.put("", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdate,
    current_admin=Depends(get_current_admin)
):
    """Update nama admin."""
    result = (
        supabase.table("admin")
        .update({"nama": body.nama})
        .eq("id", current_admin["id"])
        .select("id, nama, email, role")
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Gagal update profile")
    return result.data


# ── PUT /api/profile/password ─────────────────────────────────────
@router.put("/password")
async def update_password(
    body: PasswordUpdate,
    current_admin=Depends(get_current_admin)
):
    """
    Ganti password admin.
    Verifikasi password lama dulu dengan mencoba sign-in,
    lalu update via admin API jika valid.
    """
    # Step 1: Verifikasi password lama
    try:
        verify = supabase.auth.sign_in_with_password({
            "email": current_admin["email"],
            "password": body.password_lama,
        })
        if not verify.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password lama tidak sesuai"
            )
    except Exception as e:
        # Supabase throw exception jika credentials salah
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password lama tidak sesuai"
        )

    # Step 2: Validasi password baru
    if len(body.password_baru) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password baru minimal 8 karakter"
        )

    # Step 3: Update password via Supabase Admin API
    try:
        supabase.auth.admin.update_user_by_id(
            current_admin["id"],
            {"password": body.password_baru}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal update password: {str(e)}"
        )

    return {"message": "Password berhasil diubah"}