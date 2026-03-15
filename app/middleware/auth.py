"""
JWT Authentication & Authorization Middleware
─────────────────────────────────────────────
Decorators:
  @require_auth  → token valid (admin ATAU petugas)
  @admin_only    → token valid + role = admin

Cara kerja:
  1. Baca header  Authorization: Bearer <token>
  2. Verifikasi token dengan SUPABASE_JWT_SECRET (HS256)
  3. Lookup role dari tabel `admin` (single source of truth)
  4. Set  g.user_id  dan  g.user_role  untuk dipakai di route
"""

import os
from functools import wraps

import jwt as pyjwt
from flask import g, jsonify, request

_ERR_UNAUTH = {
    "status": "error",
    "message": "Token tidak valid atau telah kadaluarsa. Silakan login kembali.",
}
_ERR_FORBIDDEN = {
    "status": "error",
    "message": "Akses ditolak. Hanya Admin yang dapat mengakses fitur ini.",
}


def _verify_and_load_user():
    """
    Verify JWT and populate g.user_id / g.user_role.
    Returns (None) on success, or a Flask response tuple on failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify(_ERR_UNAUTH), 401

    token = auth_header.split(" ", 1)[1]
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "")

    try:
        payload = pyjwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except pyjwt.ExpiredSignatureError:
        return jsonify(_ERR_UNAUTH), 401
    except pyjwt.InvalidTokenError:
        return jsonify(_ERR_UNAUTH), 401

    user_id = payload.get("sub")
    if not user_id:
        return jsonify(_ERR_UNAUTH), 401

    # Lookup role dari tabel admin (satu-satunya kebenaran)
    from app.extensions import supabase

    try:
        res = (
            supabase.table("admin")
            .select("id, role")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception:
        return jsonify(_ERR_UNAUTH), 401

    if res.data is None:
        return jsonify(_ERR_UNAUTH), 401

    g.user_id = user_id
    g.user_role = res.data["role"]
    return None


def require_auth(f):
    """Decorator: wajib JWT valid (admin atau petugas)."""

    @wraps(f)
    def decorated(*args, **kwargs):
        err = _verify_and_load_user()
        if err:
            return err
        return f(*args, **kwargs)

    return decorated


def admin_only(f):
    """Decorator: wajib JWT valid DAN role = admin."""

    @wraps(f)
    def decorated(*args, **kwargs):
        err = _verify_and_load_user()
        if err:
            return err
        if g.user_role != "admin":
            return jsonify(_ERR_FORBIDDEN), 403
        return f(*args, **kwargs)

    return decorated
