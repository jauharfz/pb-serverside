"""
Blueprint: Autentikasi
──────────────────────
POST /api/auth/login  → REQ-AUTH-001
"""

from flask import Blueprint, jsonify, request
from gotrue.errors import AuthApiError

from app.extensions import supabase

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Field email dan password wajib diisi",
        }), 422

    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({
            "status": "error",
            "message": "Field email dan password wajib diisi",
        }), 422

    # ── Supabase Auth ─────────────────────────────────────────────────────
    try:
        auth_res = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthApiError:
        return jsonify({
            "status": "error",
            "message": "Email atau password salah",
        }), 401
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Terjadi kesalahan pada server",
        }), 500

    if not auth_res.session:
        return jsonify({
            "status": "error",
            "message": "Email atau password salah",
        }), 401

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
        return jsonify({
            "status": "error",
            "message": "Akun tidak ditemukan dalam sistem",
        }), 401

    return jsonify({
        "status": "success",
        "message": "Login berhasil",
        "data": {
            "token": auth_res.session.access_token,
            "user": admin_res.data,
        },
    }), 200
