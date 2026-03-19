"""
Blueprint: Dashboard Stats (FIXED)
────────────────────────────────────
GET /api/dashboard/stats → REQ-DASH-001 s/d REQ-DASH-004 (Admin only)

FIX 1: date.today() → tanggal WIB hari ini
  HuggingFace Spaces berjalan UTC. date.today() mengembalikan tanggal UTC
  yang berbeda dari tanggal WIB antara 00:00–06:59 WIB. View v_dashboard_stats
  menggunakan DATE(waktu_masuk AT TIME ZONE 'Asia/Jakarta') → tanggal WIB.
  Mismatch ini menyebabkan stats selalu 0 di pagi hari meskipun ada data.
"""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from app.extensions import supabase
from app.middleware.auth import require_auth

dashboard_bp = Blueprint("dashboard", __name__)


def _today_wib() -> str:
    """Tanggal hari ini dalam timezone WIB (UTC+7), format YYYY-MM-DD."""
    return (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")


@dashboard_bp.route("/dashboard/stats", methods=["GET"])
@require_auth
def get_stats():
    # [FIX] Gunakan WIB bukan UTC sebagai default tanggal
    tanggal  = request.args.get("tanggal", _today_wib())
    event_id = request.args.get("event_id", "")

    try:
        if not event_id:
            ev_res = (
                supabase.table("event")
                .select("id, nama_event")
                .filter("status", "eq", "aktif")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if not ev_res or not ev_res.data:
                return jsonify({
                    "status": "success",
                    "data": {
                        "tanggal":      tanggal,
                        "event_id":     None,
                        "nama_event":   None,
                        "total_masuk":  0,
                        "di_dalam":     0,
                        "total_keluar": 0,
                        "total_harian": 0,
                    },
                }), 200
            event_id   = ev_res.data[0]["id"]
            nama_event = ev_res.data[0]["nama_event"]
        else:
            ev_res = (
                supabase.table("event")
                .select("nama_event")
                .eq("id", event_id)
                .maybe_single()
                .execute()
            )
            nama_event = ev_res.data["nama_event"] if ev_res.data else None

        stats_res = (
            supabase.table("v_dashboard_stats")
            .select("*")
            .eq("event_id", event_id)
            .eq("tanggal",  tanggal)
            .maybe_single()
            .execute()
        )

        if stats_res and stats_res.data:
            return jsonify({"status": "success", "data": stats_res.data}), 200

        return jsonify({
            "status": "success",
            "data": {
                "tanggal":      tanggal,
                "event_id":     event_id,
                "nama_event":   nama_event,
                "total_masuk":  0,
                "di_dalam":     0,
                "total_keluar": 0,
                "total_harian": 0,
            },
        }), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500