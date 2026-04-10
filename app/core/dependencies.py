"""
core/dependencies.py
────────────────────
FastAPI dependencies untuk autentikasi dan otorisasi.
Dipakai via Depends() di endpoint yang butuh proteksi.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.client import get_supabase

_bearer = HTTPBearer(auto_error=False)

_ERR_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={
        "status": "error",
        "message": "Token tidak valid atau telah kadaluarsa. Silakan login kembali.",
    },
)
_ERR_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail={
        "status": "error",
        "message": "Akses ditolak. Hanya Admin yang dapat mengakses fitur ini.",
    },
)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    user_role: str


def _resolve_user(
    credentials: HTTPAuthorizationCredentials | None,
) -> CurrentUser:
    """Verifikasi token Bearer, kembalikan CurrentUser."""
    if not credentials:
        raise _ERR_UNAUTH

    supabase = get_supabase()
    token = credentials.credentials

    try:
        user_res = supabase.auth.get_user(token)
        if not user_res or not user_res.user:
            raise _ERR_UNAUTH
        user_id = user_res.user.id
    except HTTPException:
        raise
    except Exception:
        raise _ERR_UNAUTH

    try:
        res = (
            supabase.table("admin")
            .select("id, role")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception:
        raise _ERR_UNAUTH

    if not res or res.data is None:
        raise _ERR_UNAUTH

    return CurrentUser(user_id=user_id, user_role=res.data["role"])


# ── Public dependencies ───────────────────────────────────────────────────────

def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Endpoint boleh diakses Admin maupun Petugas."""
    return _resolve_user(credentials)


def admin_only(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Endpoint hanya boleh diakses Admin."""
    user = _resolve_user(credentials)
    if user.user_role != "admin":
        raise _ERR_FORBIDDEN
    return user
