"""
Blueprint: Member
─────────────────
GET  /api/members       → REQ-MEMBER-001  (Admin only)
POST /api/members       → REQ-MEMBER-001  (Admin only)
PUT  /api/members/<id>  → REQ-MEMBER-001  (Admin only)
"""

from flask import Blueprint, jsonify, request

from app.extensions import supabase
from app.middleware.auth import admin_only

members_bp = Blueprint("members", __name__)

# ── GET /members ──────────────────────────────────────────────────────────

@members_bp.route("/members", methods=["GET"])
@admin_only
def get_members():
    status_filter = request.args.get("status", "")
    search = (request.args.get("search") or "").strip()

    try:
        query = supabase.table("member").select("*").order("created_at", desc=True)

        if status_filter in ("aktif", "nonaktif"):
            query = query.eq("status", status_filter)

        if search:
            query = query.or_(f"nama.ilike.%{search}%,no_hp.ilike.%{search}%")

        result = query.execute()
        return jsonify({"status": "success", "data": result.data}), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── POST /members ─────────────────────────────────────────────────────────

@members_bp.route("/members", methods=["POST"])
@admin_only
def create_member():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Field nfc_uid, nama, no_hp, status, dan tanggal_daftar wajib diisi",
        }), 422

    required = ["nfc_uid", "nama", "no_hp", "status", "tanggal_daftar"]
    for field in required:
        if not data.get(field):
            return jsonify({
                "status": "error",
                "message": "Field nfc_uid, nama, no_hp, status, dan tanggal_daftar wajib diisi",
            }), 422

    if data["status"] not in ("aktif", "nonaktif"):
        return jsonify({
            "status": "error",
            "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
        }), 422

    insert_payload = {
        "nfc_uid":        data["nfc_uid"].strip(),
        "nama":           data["nama"].strip(),
        "no_hp":          data["no_hp"].strip(),
        "email":          data.get("email") or None,
        "status":         data["status"],
        "tanggal_daftar": data["tanggal_daftar"],
    }

    try:
        result = supabase.table("member").insert(insert_payload).execute()
        return jsonify({
            "status": "success",
            "message": "Member berhasil didaftarkan",
            "data": result.data[0],
        }), 201

    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            return jsonify({
                "status": "error",
                "message": "UID NFC sudah terdaftar dalam sistem",
            }), 400
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── PUT /members/<id> ─────────────────────────────────────────────────────

@members_bp.route("/members/<uuid:member_id>", methods=["PUT"])
@admin_only
def update_member(member_id):
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
        }), 422

    allowed = {"nfc_uid", "nama", "no_hp", "email", "status"}
    update_payload = {k: v for k, v in data.items() if k in allowed}

    if not update_payload:
        return jsonify({
            "status": "error",
            "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
        }), 422

    if "status" in update_payload and update_payload["status"] not in ("aktif", "nonaktif"):
        return jsonify({
            "status": "error",
            "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
        }), 422

    try:
        result = (
            supabase.table("member")
            .update(update_payload)
            .eq("id", str(member_id))
            .execute()
        )

        if not result.data:
            return jsonify({"status": "error", "message": "Member tidak ditemukan"}), 404

        return jsonify({
            "status": "success",
            "message": "Data member berhasil diupdate",
            "data": result.data[0],
        }), 200

    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            return jsonify({
                "status": "error",
                "message": "UID NFC sudah digunakan oleh member lain",
            }), 400
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500
