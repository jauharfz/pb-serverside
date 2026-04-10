"""
Router: Autentikasi & Profil Admin
────────────────────────────────────
POST /api/auth/login       → login
GET  /api/auth/me          → profil sendiri
PUT  /api/auth/profile     → update nama
PUT  /api/auth/password    → ganti password
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUser, require_auth
from app.schemas.auth import LoginRequest, UpdateNamaRequest, UpdatePasswordRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
def login(body: LoginRequest):
    return auth_service.login(email=body.email, password=body.password)


@router.get("/me")
def get_me(current_user: CurrentUser = Depends(require_auth)):
    data = auth_service.get_admin_row(current_user.user_id)
    return {"status": "success", "data": data}


@router.put("/profile")
def update_nama(
    body: UpdateNamaRequest,
    current_user: CurrentUser = Depends(require_auth),
):
    return auth_service.update_nama(user_id=current_user.user_id, nama=body.nama)


@router.put("/password")
def update_password(
    body: UpdatePasswordRequest,
    current_user: CurrentUser = Depends(require_auth),
):
    return auth_service.update_password(
        user_id=current_user.user_id,
        password_lama=body.password_lama,
        password_baru=body.password_baru,
    )
