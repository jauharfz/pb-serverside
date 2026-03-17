"""
Blueprint: Event Management
────────────────────────────
GET    /api/events       → REQ-EVENT-001  (Admin only)
POST   /api/events       → REQ-EVENT-001  (Admin only)
PATCH  /api/events/<id>  → REQ-EVENT-001  (Admin only)
DELETE /api/events/<id>  → REQ-EVENT-001  (Admin only)

Aturan bisnis (semua ditegakkan di backend):

  [POST]
  - Tanggal hari ini   → status otomatis 'aktif', nonaktifkan event aktif lain
  - Tanggal masa depan → status otomatis 'selesai' (belum mulai)

  [PATCH — deteksi operasi dari isi body]
  A. body berisi 'status' → toggle aktif/selesai
     - Aktifkan: hanya boleh jika tanggal event <= hari ini
     - Aktifkan: otomatis nonaktifkan event aktif lain
  B. body berisi field detail (nama_event, lokasi, tanggal) → edit
     - Tanggal TIDAK boleh diubah jika event sedang 'aktif'
     - Jika edit tanggal → hari ini: status otomatis jadi 'aktif' + nonaktifkan lain
     - Jika edit tanggal → masa depan: status otomatis jadi 'selesai'
     - Jika edit tanggal → masa lalu: status tetap 'selesai'

  [DELETE]
  - Event aktif tidak bisa dihapus
  - Event dengan kunjungan tidak bisa dihapus (FK RESTRICT dari Supabase)

  Invariant: hanya satu event 'aktif' di satu waktu.
"""

import re
from datetime import date

from flask import Blueprint, jsonify, request

from app.extensions import supabase
from app.middleware.auth import admin_only

events_bp = Blueprint("events", __name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _today():
    return date.today().isoformat()


def _deactivate_other_events(exclude_id=None):
    """Nonaktifkan semua event aktif kecuali exclude_id."""
    query = (
        supabase.table("event")
        .update({"status": "selesai"})
        .eq("status", "aktif")
    )
    if exclude_id:
        query = query.neq("id", exclude_id)
    query.execute()


# ── GET /events ───────────────────────────────────────────────────────────

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

    today       = _today()
    # Hanya tanggal hari ini persis yang auto-aktif.
    # Tanggal lampau → selesai (event baru dengan tanggal lalu tidak masuk akal untuk diaktifkan).
    auto_status = "aktif" if tanggal == today else "selesai"

    try:
        if auto_status == "aktif":
            _deactivate_other_events(exclude_id=None)

        result = (
            supabase.table("event")
            .insert({
                "nama_event": nama_event,
                "tanggal":    tanggal,
                "lokasi":     lokasi,
                "status":     auto_status,
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
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── PATCH /events/<id> ────────────────────────────────────────────────────

@events_bp.route("/events/<string:event_id>", methods=["PATCH"])
@admin_only
def update_event(event_id):
    body = request.get_json(silent=True) or {}

    # Ambil data event saat ini
    try:
        check = (
            supabase.table("event")
            .select("id, status, tanggal")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404
    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

    current = check.data

    if "status" in body:
        return _handle_toggle_status(event_id, body, current)
    else:
        return _handle_edit_fields(event_id, body, current)


def _handle_toggle_status(event_id, body, current):
    new_status = (body.get("status") or "").strip()

    if new_status not in ("aktif", "selesai"):
        return jsonify({
            "status": "error",
            "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'",
        }), 400

    # Guard: event masa depan tidak boleh diaktifkan
    if new_status == "aktif" and current["tanggal"] > _today():
        return jsonify({
            "status": "error",
            "message": (
                f"Event ini dijadwalkan pada {current['tanggal']} dan belum bisa diaktifkan. "
                "Aktifkan hanya pada hari pelaksanaan."
            ),
        }), 422

    try:
        if new_status == "aktif":
            _deactivate_other_events(exclude_id=event_id)

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
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


def _handle_edit_fields(event_id, body, current):
    ALLOWED = {"nama_event", "lokasi", "tanggal"}
    payload = {k: v for k, v in body.items() if k in ALLOWED and v is not None}

    if not payload:
        return jsonify({
            "status": "error",
            "message": "Tidak ada field yang valid untuk diperbarui",
        }), 422

    # Guard: tanggal tidak boleh diubah jika event sedang aktif
    if "tanggal" in payload and current["status"] == "aktif":
        return jsonify({
            "status": "error",
            "message": "Tanggal tidak dapat diubah saat event sedang aktif. Nonaktifkan event terlebih dahulu.",
        }), 422

    if "tanggal" in payload and not _DATE_RE.match(payload["tanggal"]):
        return jsonify({
            "status": "error",
            "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD",
        }), 422

    # Jika tanggal diubah, tentukan status baru otomatis
    today = _today()
    if "tanggal" in payload:
        new_tanggal    = payload["tanggal"]
        # Sama: hanya tanggal hari ini yang auto-aktif. Tanggal lampau → selesai.
        new_auto_status = "aktif" if new_tanggal == today else "selesai"
        payload["status"] = new_auto_status

        # Jika event baru akan aktif, nonaktifkan event lain
        if new_auto_status == "aktif":
            _deactivate_other_events(exclude_id=event_id)

    try:
        result = (
            supabase.table("event")
            .update(payload)
            .eq("id", event_id)
            .execute()
        )
        updated = result.data[0] if result.data else {}
        return jsonify({
            "status":  "success",
            "message": "Data event berhasil diperbarui",
            "data":    updated,
        }), 200
    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── DELETE /events/<id> ───────────────────────────────────────────────────

@events_bp.route("/events/<string:event_id>", methods=["DELETE"])
@admin_only
def delete_event(event_id):
    try:
        check = (
            supabase.table("event")
            .select("id, status")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404

        if check.data.get("status") == "aktif":
            return jsonify({
                "status": "error",
                "message": "Event yang sedang aktif tidak dapat dihapus. Nonaktifkan terlebih dahulu.",
            }), 409

        result = (
            supabase.table("event")
            .delete()
            .eq("id", event_id)
            .execute()
        )

        if result.data is not None and len(result.data) == 0:
            return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404

        return jsonify({"status": "success", "message": "Event berhasil dihapus"}), 200

    except Exception as exc:
        msg = str(exc).lower()
        if "foreign key" in msg or "restrict" in msg or "kunjungan" in msg:
            return jsonify({
                "status": "error",
                "message": "Event tidak dapat dihapus karena sudah memiliki data kunjungan.",
            }), 409
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500