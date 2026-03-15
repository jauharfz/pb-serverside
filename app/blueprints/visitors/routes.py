"""
Blueprint: Pengunjung
─────────────────────
GET  /api/visitors         → Admin only
POST /api/visitors/manual  → REQ-MANUAL-001, REQ-MANUAL-002  (Admin & Petugas)

Logika keluar manual:
  Saat petugas menekan tombol KELUAR, sistem mengambil kunjungan
  pengunjung biasa yang paling lama berada di dalam (FIFO) untuk
  di-update waktu_keluar-nya.
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, g

from app.extensions import supabase
from app.middleware.auth import admin_only, require_auth

visitors_bp = Blueprint("visitors", __name__)


# ── GET /visitors ─────────────────────────────────────────────────────────

@visitors_bp.route("/visitors", methods=["GET"])
@admin_only
def get_visitors():
    tanggal   = request.args.get("tanggal", "")
    event_id  = request.args.get("event_id", "")
    tipe      = request.args.get("tipe_pengunjung", "")
    status    = request.args.get("status", "")

    try:
        query = supabase.table("kunjungan").select("*").order("waktu_masuk", desc=True)

        if event_id:
            query = query.eq("event_id", event_id)
        if tipe in ("member", "biasa"):
            query = query.eq("tipe_pengunjung", tipe)
        if status in ("di_dalam", "keluar"):
            query = query.eq("status", status)
        if tanggal:
            query = (
                query
                .gte("waktu_masuk", f"{tanggal}T00:00:00+07:00")
                .lte("waktu_masuk", f"{tanggal}T23:59:59+07:00")
            )

        result = query.execute()
        return jsonify({"status": "success", "data": result.data}), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── POST /visitors/manual ─────────────────────────────────────────────────

@visitors_bp.route("/visitors/manual", methods=["POST"])
@require_auth  # Admin dan Petugas
def manual_visitor():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "message": "Field aksi dan event_id wajib diisi",
        }), 422

    aksi     = (data.get("aksi") or "").strip()
    event_id = (data.get("event_id") or "").strip()

    if aksi not in ("masuk", "keluar"):
        return jsonify({
            "status": "error",
            "message": "Field aksi harus berupa 'masuk' atau 'keluar'",
        }), 422

    if not event_id:
        return jsonify({
            "status": "error",
            "message": "Field aksi dan event_id wajib diisi",
        }), 422

    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        if aksi == "masuk":
            # Insert kunjungan biasa baru
            result = (
                supabase.table("kunjungan")
                .insert({
                    "event_id":        event_id,
                    "member_id":       None,
                    "tipe_pengunjung": "biasa",
                    "waktu_masuk":     now,
                    "waktu_keluar":    None,
                    "status":          "di_dalam",
                    "dicatat_oleh":    g.user_id,
                })
                .execute()
            )
            message = "Pengunjung biasa masuk berhasil dicatat"

        else:
            # Cari kunjungan biasa tertua yang masih di_dalam (FIFO)
            find_res = (
                supabase.table("kunjungan")
                .select("id")
                .eq("event_id", event_id)
                .eq("tipe_pengunjung", "biasa")
                .eq("status", "di_dalam")
                .order("waktu_masuk")
                .limit(1)
                .execute()
            )

            if not find_res.data:
                return jsonify({
                    "status": "error",
                    "message": "Tidak ada pengunjung biasa yang sedang di dalam",
                }), 404

            kunjungan_id = find_res.data[0]["id"]
            result = (
                supabase.table("kunjungan")
                .update({"waktu_keluar": now})
                .eq("id", kunjungan_id)
                .execute()
            )
            message = "Pengunjung biasa keluar berhasil dicatat"

        if not result.data:
            return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500

        return jsonify({
            "status": "success",
            "message": message,
            "data": result.data[0],
        }), 201

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500
