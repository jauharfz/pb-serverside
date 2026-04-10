"""
services/visitor_service.py
────────────────────────────
Business logic untuk pencatatan kunjungan manual (pengunjung biasa).
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.db.client import get_supabase

logger = logging.getLogger(__name__)


def list_visitors(
    tanggal: str,
    event_id: str,
    tipe_pengunjung: str,
    visitor_status: str,
    limit: int,
    offset: int,
) -> dict:
    supabase = get_supabase()
    try:
        query = (
            supabase.table("kunjungan")
            .select("*, member:member_id(nama)")
            .order("waktu_masuk", desc=True)
            .range(offset, offset + limit - 1)
        )
        if event_id:
            query = query.eq("event_id", event_id)
        if tipe_pengunjung in ("member", "biasa"):
            query = query.eq("tipe_pengunjung", tipe_pengunjung)
        if visitor_status in ("di_dalam", "keluar"):
            query = query.eq("status", visitor_status)
        if tanggal:
            query = (
                query
                .gte("waktu_masuk", f"{tanggal}T00:00:00+07:00")
                .lte("waktu_masuk", f"{tanggal}T23:59:59+07:00")
            )
        result = query.execute()
        return {"status": "success", "data": result.data}
    except Exception:
        logger.exception("Error fetching visitors")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def manual_visitor(aksi: str, event_id: str, user_id: str) -> dict:
    supabase = get_supabase()
    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        if aksi == "masuk":
            result = (
                supabase.table("kunjungan")
                .insert({
                    "event_id": event_id,
                    "member_id": None,
                    "tipe_pengunjung": "biasa",
                    "waktu_masuk": now,
                    "waktu_keluar": None,
                    "status": "di_dalam",
                    "dicatat_oleh": user_id,
                })
                .execute()
            )
            message = "Pengunjung biasa masuk berhasil dicatat"

        else:  # keluar
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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "status": "error",
                        "message": "Tidak ada pengunjung biasa yang sedang di dalam",
                    },
                )
            kunjungan_id = find_res.data[0]["id"]
            result = (
                supabase.table("kunjungan")
                .update({"waktu_keluar": now})
                .eq("id", kunjungan_id)
                .execute()
            )
            message = "Pengunjung biasa keluar berhasil dicatat"

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status": "error", "message": "Terjadi kesalahan pada server"},
            )

        return {"status": "success", "message": message, "data": result.data[0]}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error recording manual visitor aksi=%s event=%s", aksi, event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
