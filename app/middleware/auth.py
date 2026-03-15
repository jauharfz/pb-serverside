"""
JWT Authentication & Authorization Middleware
─────────────────────────────────────────────
Verifikasi token dilakukan via Supabase Auth API (get_user),
bukan decode manual — agar kompatibel dengan semua algoritma
signing termasuk ECC P-256 yang baru dipakai Supabase.
"""

from functools import wraps
from flask import g, jsonify, request
from app.extensions import supabase

_ERR_UNAUTH = {
    "status": "error",
    "message": "Token tidak valid atau telah kadaluarsa. Silakan login kembali.",
}
_ERR_FORBIDDEN = {
    "status": "error",
    "message": "Akses ditolak. Hanya Admin yang dapat mengakses fitur ini.",
}


def _verify_and_load_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify(_ERR_UNAUTH), 401

    token = auth_header.split(" ", 1)[1]

    try:
        # Tanya Supabase langsung — tidak perlu decode manual
        user_res = supabase.auth.get_user(token)
        if not user_res or not user_res.user:
            return jsonify(_ERR_UNAUTH), 401
        user_id = user_res.user.id
    except Exception:
        return jsonify(_ERR_UNAUTH), 401

    # Lookup role dari tabel admin
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

    if not res or res.data is None:
        return jsonify(_ERR_UNAUTH), 401

    g.user_id   = user_id
    g.user_role = res.data["role"]
    return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        err = _verify_and_load_user()
        if err:
            return err
        return f(*args, **kwargs)
    return decorated


def admin_only(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        err = _verify_and_load_user()
        if err:
            return err
        if g.user_role != "admin":
            return jsonify(_ERR_FORBIDDEN), 403
        return f(*args, **kwargs)
    return decorated
