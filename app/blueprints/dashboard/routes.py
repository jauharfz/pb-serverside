"""
Blueprint: Dashboard Stats
──────────────────────────
GET /api/dashboard/stats → REQ-DASH-001, REQ-DASH-002, REQ-DASH-003, REQ-DASH-004
                           (Admin only)

Data bersumber dari view v_dashboard_stats di Supabase.
Jika belum ada kunjungan untuk hari/event tersebut,
endpoint tetap mengembalikan objek dengan nilai counter = 0.
"""

from datetime import date

from flask import Blueprint, jsonify, request

from app.extensions import supabase
from app.middleware.auth import admin_only

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard/stats", methods=["GET"])
@admin_only
def get_stats():
    tanggal  = request.args.get("tanggal", str(date.today()))
    event_id = request.args.get("event_id", "")

    try:
        # Resolve event_id jika tidak dikirim
        if not event_id:
            ev_res = (
                supabase.table("event")
                .select("id, nama_event")
                .filter("status", "eq", "aktif")   # ganti .eq() → .filter()
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if not ev_res or not ev_res.data:      # tambah guard not ev_res
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
            # Ambil nama event jika event_id eksplisit dikirim
            ev_res = (
                supabase.table("event")
                .select("nama_event")
                .eq("id", event_id)
                .maybe_single()
                .execute()
            )
            nama_event = ev_res.data["nama_event"] if ev_res.data else None

        # Query view v_dashboard_stats
        stats_res = (
            supabase.table("v_dashboard_stats")
            .select("*")
            .eq("event_id", event_id)
            .eq("tanggal", tanggal)
            .maybe_single()
            .execute()
        )

        if stats_res and stats_res.data:       # tambah guard stats_res
            return jsonify({"status": "success", "data": stats_res.data}), 200

        # Event ada tapi belum ada kunjungan hari ini → kembalikan nol
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
