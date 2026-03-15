"""
Blueprint: Diskon UMKM
──────────────────────
GET /api/discounts → REQ-MEMBER-002  (Admin & Petugas)

Membaca tabel diskon_member + tenant_umkm (join via PostgREST).
"""

from flask import Blueprint, jsonify, request

from app.extensions import supabase
from app.middleware.auth import require_auth

discounts_bp = Blueprint("discounts", __name__)


@discounts_bp.route("/discounts", methods=["GET"])
@require_auth
def get_discounts():
    is_aktif_str = (request.args.get("is_aktif") or "true").lower()
    tenant_id    = request.args.get("tenant_id", "")

    try:
        # PostgREST join: select diskon + nested tenant object
        query = (
            supabase.table("diskon_member")
            .select("*, tenant:tenant_umkm(*)")
            .order("berlaku_mulai", desc=True)
        )

        if is_aktif_str == "true":
            query = query.eq("is_aktif", True)
        elif is_aktif_str == "false":
            query = query.eq("is_aktif", False)

        if tenant_id:
            query = query.eq("tenant_id", tenant_id)

        result = query.execute()
        return jsonify({"status": "success", "data": result.data}), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500
