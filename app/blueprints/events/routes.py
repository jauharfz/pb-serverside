"""
Blueprint: Event Management
────────────────────────────
GET   /api/events       → REQ-EVENT-001  (Admin only)
POST  /api/events       → REQ-EVENT-001  (Admin only)
PATCH /api/events/<id>  → REQ-EVENT-001  (Admin only)
DELETE /api/events/<id> → REQ-EVENT-001  (Admin only)

Aturan bisnis:
  - Event dibuat hari ini    → status otomatis 'aktif'
  - Event dibuat masa depan  → status otomatis 'selesai' (belum mulai)
  - Hanya satu event boleh 'aktif' bersamaan — mengaktifkan satu event
    akan otomatis menonaktifkan event lain yang sedang aktif
  - PATCH mendeteksi operasi dari isi body:
      body berisi 'status' → toggle aktif/selesai
      body berisi field lain (nama_event, lokasi, tanggal) → edit detail
  - DELETE hanya berhasil jika event belum punya kunjungan (FK RESTRICT)

Tidak ada perubahan schema database — tabel EVENT dan enum
event_status_enum ('aktif', 'selesai') sudah ada di Supabase schema.
"""

import re
from datetime import date

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
            .order("status", desc=False)   # 'aktif' < 'selesai' alfabet → aktif dulu
            .order("tanggal", desc=True)
            .execute()
        )
        return jsonify({"status": "success", "data": result.data or []}), 200
    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── POST /events ──────────────────────────────────────────────────────────
# Status ditentukan otomatis berdasarkan tanggal:
#   tanggal == hari ini → 'aktif'
#   tanggal > hari ini  → 'selesai' (belum mulai, tidak menerima kunjungan)
# Jika event dibuat aktif (tanggal hari ini), event aktif lain dinonaktifkan.

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

    # Tentukan status berdasarkan tanggal
    today        = date.today().isoformat()
    auto_status  = "aktif" if tanggal == today else "selesai"

    try:
        # Jika event baru akan aktif, nonaktifkan event lain yang sedang aktif
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
# Mendeteksi operasi dari isi body:
#   body mengandung 'status'     → toggle aktif/selesai
#   body mengandung field detail → edit nama_event, lokasi, tanggal

@events_bp.route("/events/<string:event_id>", methods=["PATCH"])
@admin_only
def update_event(event_id):
    body = request.get_json(silent=True) or {}

    # ── Cek keberadaan event ──────────────────────────────────────────────
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
    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

    # ── Deteksi operasi ───────────────────────────────────────────────────
    if "status" in body:
        return _handle_toggle_status(event_id, body, check.data)
    else:
        return _handle_edit_fields(event_id, body)


def _handle_toggle_status(event_id, body, current_event):
    """Toggle status: aktif ↔ selesai."""
    new_status = (body.get("status") or "").strip()

    if new_status not in ("aktif", "selesai"):
        return jsonify({
            "status": "error",
            "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'",
        }), 400

    try:
        # Jika mengaktifkan, nonaktifkan event lain yang sedang aktif
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


def _handle_edit_fields(event_id, body):
    """Edit detail: nama_event, lokasi, tanggal."""
    ALLOWED = {"nama_event", "lokasi", "tanggal"}
    payload = {k: v for k, v in body.items() if k in ALLOWED and v is not None}

    if not payload:
        return jsonify({
            "status": "error",
            "message": "Tidak ada field yang valid untuk diperbarui",
        }), 422

    # Validasi format tanggal jika disertakan
    if "tanggal" in payload and not _DATE_RE.match(payload["tanggal"]):
        return jsonify({
            "status": "error",
            "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD",
        }), 422

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
# Postgres FK RESTRICT pada kunjungan.event_id akan menolak jika ada kunjungan.
# Frontend mendeteksi error ini dari status 409 atau pesan error yang mengandung
# kata kunci 'kunjungan' / 'restrict'.

@events_bp.route("/events/<string:event_id>", methods=["DELETE"])
@admin_only
def delete_event(event_id):
    try:
        # Pastikan event ada
        check = (
            supabase.table("event")
            .select("id, status")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404

        # Jangan hapus event yang masih aktif
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

        # Supabase delete yang kena FK RESTRICT biasanya raise exception,
        # tapi jika result kosong karena alasan lain, kembalikan 404
        if result.data is not None and len(result.data) == 0:
            return jsonify({"status": "error", "message": "Event tidak ditemukan"}), 404

        return jsonify({"status": "success", "message": "Event berhasil dihapus"}), 200

    except Exception as exc:
        msg = str(exc).lower()
        if "violates foreign key" in msg or "restrict" in msg or "kunjungan" in msg:
            return jsonify({
                "status": "error",
                "message": "Event tidak dapat dihapus karena sudah memiliki data kunjungan.",
            }), 409
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── Helper ────────────────────────────────────────────────────────────────

def _deactivate_other_events(exclude_id):
    """
    Nonaktifkan semua event aktif kecuali exclude_id.
    Dipanggil sebelum mengaktifkan event baru untuk menjaga
    invariant: hanya satu event aktif di satu waktu.
    """
    query = (
        supabase.table("event")
        .update({"status": "selesai"})
        .eq("status", "aktif")
    )
    if exclude_id:
        query = query.neq("id", exclude_id)
    query.execute()