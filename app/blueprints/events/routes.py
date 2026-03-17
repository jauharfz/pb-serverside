"""
Blueprint: Event Management
────────────────────────────
GET    /api/events       → REQ-EVENT-001  (Admin only)
POST   /api/events       → REQ-EVENT-001  (Admin only)
PATCH  /api/events/<id>  → REQ-EVENT-001  (Admin only)
DELETE /api/events/<id>  → REQ-EVENT-001  (Admin only, hanya jika 0 kunjungan)
"""

import re

from flask import Blueprint, jsonify, request

from app.extensions import supabase
from app.middleware.auth import admin_only

events_bp = Blueprint("events", __name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── GET /events ───────────────────────────────────────────────────────────

@events_bp.route("/events", methods=["GET"])
@admin_only
def get_events():
    try:
        result = (
            supabase.table("event")
            .select("*")
            .order("status", desc=False)   # 'aktif' < 'selesai' → aktif dulu
            .order("tanggal", desc=True)
            .execute()
        )
        return jsonify({"status": "success", "data": result.data or []}), 200
    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── POST /events ──────────────────────────────────────────────────────────

@events_bp.route("/events", methods=["POST"])
@admin_only
def create_event():
    body = request.get_json(silent=True) or {}

    nama_event = (body.get("nama_event") or "").strip()
    tanggal    = (body.get("tanggal")    or "").strip()
    lokasi     = (body.get("lokasi")     or "").strip()

    if not nama_event or not tanggal or not lokasi:
        return jsonify({
            "status": "error",
            "message": "Field nama_event, tanggal (YYYY-MM-DD), dan lokasi wajib diisi",
        }), 422

    if not _DATE_RE.match(tanggal):
        return jsonify({
            "status": "error",
            "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD",
        }), 422

    try:
        result = (
            supabase.table("event")
            .insert({"nama_event": nama_event, "tanggal": tanggal,
                     "lokasi": lokasi, "status": "aktif"})
            .execute()
        )
        return jsonify({
            "status": "success", "message": "Event berhasil dibuat",
            "data": result.data[0] if result.data else {},
        }), 201
    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── PATCH /events/<id> ────────────────────────────────────────────────────
# Mendukung dua use-case:
#   1. Toggle status:    body = { "status": "aktif" | "selesai" }
#   2. Edit nama/lokasi: body = { "nama_event": "...", "lokasi": "..." }
# Tanggal tidak dapat diubah melalui endpoint ini.

@events_bp.route("/events/<string:event_id>", methods=["PATCH"])
@admin_only
def update_event(event_id):
    body = request.get_json(silent=True) or {}

    update_payload = {}

    if "status" in body:
        new_status = (body["status"] or "").strip()
        if new_status not in ("aktif", "selesai"):
            return jsonify({
                "status": "error",
                "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'",
            }), 400
        update_payload["status"] = new_status

    if "nama_event" in body:
        nama = (body["nama_event"] or "").strip()
        if not nama:
            return jsonify({"status": "error", "message": "nama_event tidak boleh kosong"}), 422
        update_payload["nama_event"] = nama

    if "lokasi" in body:
        lokasi = (body["lokasi"] or "").strip()
        if not lokasi:
            return jsonify({"status": "error", "message": "lokasi tidak boleh kosong"}), 422
        update_payload["lokasi"] = lokasi

    if not update_payload:
        return jsonify({
            "status": "error",
            "message": "Tidak ada field yang valid untuk diupdate",
        }), 422

    try:
        check = (
            supabase.table("event")
            .select("id")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404

        result = (
            supabase.table("event")
            .update(update_payload)
            .eq("id", event_id)
            .execute()
        )
        updated = result.data[0] if result.data else {}

        if "status" in update_payload:
            msg = f"Status event berhasil diubah menjadi {update_payload['status']}"
        else:
            msg = "Data event berhasil diperbarui"

        return jsonify({"status": "success", "message": msg, "data": updated}), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── DELETE /events/<id> ───────────────────────────────────────────────────
# Guard berlapis:
#   1. Event tidak boleh masih aktif
#   2. Event tidak boleh sudah punya kunjungan (ON DELETE RESTRICT di schema)
# Jika keduanya lolos → hapus aman.

@events_bp.route("/events/<string:event_id>", methods=["DELETE"])
@admin_only
def delete_event(event_id):
    try:
        # Cek event ada
        check = (
            supabase.table("event")
            .select("id, nama_event, status")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404

        # Tolak hapus event aktif
        if check.data.get("status") == "aktif":
            return jsonify({
                "status": "error",
                "message": "Event yang masih aktif tidak dapat dihapus. Nonaktifkan terlebih dahulu.",
            }), 409

        # Cek keberadaan kunjungan
        kunjungan_check = (
            supabase.table("kunjungan")
            .select("id")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )
        if kunjungan_check.data:
            return jsonify({
                "status": "error",
                "message": "Event tidak dapat dihapus karena sudah memiliki data kunjungan. "
                           "Tandai sebagai 'selesai' untuk mengarsipkan.",
            }), 409

        # Aman dihapus
        supabase.table("event").delete().eq("id", event_id).execute()
        return jsonify({"status": "success", "message": "Event berhasil dihapus"}), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500