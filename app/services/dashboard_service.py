"""
services/dashboard_service.py
───────────────────────────────
Business logic untuk statistik dashboard.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.db.client import get_supabase

logger = logging.getLogger(__name__)


def _today_wib() -> str:
    """Tanggal hari ini WIB (UTC+7), format YYYY-MM-DD."""
    return (datetime.now(tz=timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d")


def get_stats(tanggal: str, event_id: str) -> dict:
    """Ambil statistik dashboard untuk tanggal dan event tertentu."""
    supabase = get_supabase()
    tanggal = tanggal or _today_wib()

    try:
        nama_event: str | None = None

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
                        "tanggal": tanggal,
                        "event_id": None,
                        "nama_event": None,
                        "total_masuk": 0,
                        "di_dalam": 0,
                        "total_keluar": 0,
                        "total_harian": 0,
                    },
                }
            event_id = ev_res.data[0]["id"]
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
            .eq("tanggal", tanggal)
            .maybe_single()
            .execute()
        )

        if stats_res and stats_res.data:
            return {"status": "success", "data": stats_res.data}

        return {
            "status": "success",
            "data": {
                "tanggal": tanggal,
                "event_id": event_id,
                "nama_event": nama_event,
                "total_masuk": 0,
                "di_dalam": 0,
                "total_keluar": 0,
                "total_harian": 0,
            },
        }

    except Exception:
        logger.exception("Error fetching dashboard stats")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
