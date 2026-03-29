"""
Router: Dashboard Stats
────────────────────────
GET /api/dashboard/stats → REQ-DASH-001 s/d REQ-DASH-004 (Admin & Petugas)

Menggunakan tanggal WIB (UTC+7) sebagai default, bukan UTC,
agar sinkron dengan view v_dashboard_stats yang menggunakan
DATE(waktu_masuk AT TIME ZONE 'Asia/Jakarta').
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import CurrentUser, require_auth, supabase

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _today_wib() -> str:
    """Tanggal hari ini dalam timezone WIB (UTC+7), format YYYY-MM-DD."""
    return (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")


@router.get("/stats")
def get_stats(
    tanggal: str = Query(""),
    event_id: str = Query(""),
    _user: CurrentUser = Depends(require_auth),
):
    tanggal = tanggal or _today_wib()

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
                return {
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
                }
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
            return {"status": "success", "data": stats_res.data}

        return {
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
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
