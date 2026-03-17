"""
Blueprint: Event Management
────────────────────────────
GET   /api/events       → REQ-EVENT-001  (Admin only)
POST  /api/events       → REQ-EVENT-001  (Admin only)
PATCH /api/events/<id>  → REQ-EVENT-001  (Admin only)

Tidak ada perubahan schema database — tabel EVENT dan enum
event_status_enum ('aktif', 'selesai') sudah ada di Supabase schema.
"""

import re

from flask import Blueprint, jsonify, request

from app.extensions import supabase
from app.middleware.auth import admin_only

events_bp = Blueprint("events", __name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── GET /events ───────────────────────────────────────────────────────────
# Mengembalikan semua event.
# Urutan: aktif dulu ('aktif' < 'selesai' secara alfabet → order asc),
#         dalam tiap grup: tanggal terbaru dulu (order desc).

@events_bp.route("/events", methods=["GET"])
@admin_only
def get_events():
    try:
        result = (
            supabase.table("event")
            .select("*")
            .order("status", desc=False)
            .order("tanggal", desc=True)
            .execute()
        )
        return jsonify({
            "status": "success",
            "data": result.data or [],
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Terjadi kesalahan pada server",
        }), 500


# ── POST /events ──────────────────────────────────────────────────────────
# Membuat event baru dengan status otomatis 'aktif'.
# Body: { nama_event: str, tanggal: "YYYY-MM-DD", lokasi: str }

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
            .insert({
                "nama_event": nama_event,
                "tanggal":    tanggal,
                "lokasi":     lokasi,
                "status":     "aktif",
            })
            .execute()
        )
        created = result.data[0] if result.data else {}
        return jsonify({
            "status":  "success",
            "message": "Event berhasil dibuat",
            "data":    created,
        }), 201

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Terjadi kesalahan pada server",
        }), 500


# ── PATCH /events/<id> ────────────────────────────────────────────────────
# Mengubah status event: 'aktif' ↔ 'selesai'.
# Hanya field 'status' yang diterima.
# Body: { status: "aktif" | "selesai" }

@events_bp.route("/events/<string:event_id>", methods=["PATCH"])
@admin_only
def update_event_status(event_id):
    body       = request.get_json(silent=True) or {}
    new_status = (body.get("status") or "").strip()

    if new_status not in ("aktif", "selesai"):
        return jsonify({
            "status": "error",
            "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'",
        }), 400

    try:
        # Cek keberadaan event
        check = (
            supabase.table("event")
            .select("id")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            return jsonify({
                "status": "error",
                "message": "Event tidak ditemukan",
            }), 404

        # Update status
        result = (
            supabase.table("event")
            .update({"status": new_status})
            .eq("id", event_id)
            .execute()
        )
        updated = result.data[0] if result.data else {}
        return jsonify({
            "status":  "success",
            "message": f"Status event berhasil diubah menjadi {new_status}",
            "data":    updated,
        }), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Terjadi kesalahan pada server",
        }), 500