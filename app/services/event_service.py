"""
services/event_service.py
──────────────────────────
Business logic untuk manajemen event.

Aturan bisnis:
  [POST]  Tanggal hari ini → 'aktif', nonaktifkan lainnya.
          Tanggal lain     → 'selesai'.
  [PATCH] body berisi 'status' → toggle aktif/selesai.
          body berisi field lain → edit detail.
  [DELETE] Event aktif tidak bisa dihapus.
           Event dengan kunjungan tidak bisa dihapus (FK RESTRICT).
  Invariant: hanya satu event 'aktif' di satu waktu.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.db.client import get_supabase
from app.schemas.events import PatchEventRequest

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _today() -> str:
    """Tanggal hari ini WIB (UTC+7), format YYYY-MM-DD."""
    return (datetime.now(tz=timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%d")


def _deactivate_other_events(exclude_id: Optional[str] = None) -> None:
    """Nonaktifkan semua event aktif kecuali exclude_id."""
    supabase = get_supabase()
    query = (
        supabase.table("event")
        .update({"status": "selesai"})
        .eq("status", "aktif")
    )
    if exclude_id:
        query = query.neq("id", exclude_id)
    query.execute()


def get_public_event() -> dict:
    """Kembalikan event aktif atau event mendatang terdekat (tanpa auth)."""
    supabase = get_supabase()
    today = _today()
    try:
        aktif_res = (
            supabase.table("event")
            .select("id, nama_event, tanggal, lokasi, status")
            .eq("status", "aktif")
            .order("tanggal", desc=False)
            .limit(1)
            .execute()
        )
        if aktif_res.data:
            return {"status": "success", "data": aktif_res.data[0]}

        upcoming_res = (
            supabase.table("event")
            .select("id, nama_event, tanggal, lokasi, status")
            .eq("status", "selesai")
            .gt("tanggal", today)
            .order("tanggal", desc=False)
            .limit(1)
            .execute()
        )
        if upcoming_res.data:
            return {"status": "success", "data": upcoming_res.data[0]}

        return {"status": "success", "data": None}
    except Exception:
        return {"status": "success", "data": None}


def list_events() -> dict:
    supabase = get_supabase()
    try:
        result = (
            supabase.table("event")
            .select("*")
            .order("status", desc=False)
            .order("tanggal", desc=True)
            .execute()
        )
        return {"status": "success", "data": result.data or []}
    except Exception:
        logger.exception("Error fetching events")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def create_event(nama_event: str, tanggal: str, lokasi: str) -> dict:
    supabase = get_supabase()
    today = _today()
    auto_status = "aktif" if tanggal == today else "selesai"

    try:
        if auto_status == "aktif":
            _deactivate_other_events()

        result = (
            supabase.table("event")
            .insert({
                "nama_event": nama_event,
                "tanggal": tanggal,
                "lokasi": lokasi,
                "status": auto_status,
            })
            .execute()
        )
        created = result.data[0] if result.data else {}
        return {"status": "success", "message": "Event berhasil dibuat", "data": created}
    except Exception:
        logger.exception("Error creating event")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def _fetch_event_or_404(event_id: str) -> dict:
    supabase = get_supabase()
    try:
        check = (
            supabase.table("event")
            .select("id, status, tanggal")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Event tidak ditemukan"},
            )
        return check.data
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching event %s", event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def patch_event(event_id: str, body: PatchEventRequest) -> dict:
    current = _fetch_event_or_404(event_id)
    if body.status is not None:
        return _toggle_status(event_id, body.status, current)
    return _edit_fields(event_id, body, current)


def _toggle_status(event_id: str, new_status: str, current: dict) -> dict:
    supabase = get_supabase()
    new_status = new_status.strip()

    if new_status not in ("aktif", "selesai"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'",
            },
        )

    if new_status == "aktif" and current["tanggal"] > _today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": (
                    f"Event ini dijadwalkan pada {current['tanggal']} dan belum bisa diaktifkan. "
                    "Aktifkan hanya pada hari pelaksanaan."
                ),
            },
        )

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
        return {
            "status": "success",
            "message": f"Status event berhasil diubah menjadi {new_status}",
            "data": updated,
        }
    except Exception:
        logger.exception("Error toggling event status %s", event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def _edit_fields(event_id: str, body: PatchEventRequest, current: dict) -> dict:
    supabase = get_supabase()
    ALLOWED = {"nama_event", "lokasi", "tanggal"}
    payload = {
        k: v
        for k, v in body.model_dump(exclude_none=True).items()
        if k in ALLOWED
    }

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Tidak ada field yang valid untuk diperbarui"},
        )

    if "tanggal" in payload and current["status"] == "aktif":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": "Tanggal tidak dapat diubah saat event sedang aktif. Nonaktifkan event terlebih dahulu.",
            },
        )

    if "tanggal" in payload and not _DATE_RE.match(payload["tanggal"]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD",
            },
        )

    today = _today()
    if "tanggal" in payload:
        new_tanggal = payload["tanggal"]
        new_auto_status = "aktif" if new_tanggal == today else "selesai"
        payload["status"] = new_auto_status
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
        return {"status": "success", "message": "Data event berhasil diperbarui", "data": updated}
    except Exception:
        logger.exception("Error editing event %s", event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def delete_event(event_id: str) -> dict:
    supabase = get_supabase()
    try:
        check = (
            supabase.table("event")
            .select("id, status")
            .eq("id", event_id)
            .maybe_single()
            .execute()
        )
        if not check.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Event tidak ditemukan"},
            )

        if check.data.get("status") == "aktif":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "status": "error",
                    "message": "Event yang sedang aktif tidak dapat dihapus. Nonaktifkan terlebih dahulu.",
                },
            )

        result = supabase.table("event").delete().eq("id", event_id).execute()

        if result.data is not None and len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Event tidak ditemukan"},
            )

        return {"status": "success", "message": "Event berhasil dihapus"}

    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "foreign key" in msg or "restrict" in msg or "kunjungan" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "status": "error",
                    "message": "Event tidak dapat dihapus karena sudah memiliki data kunjungan.",
                },
            )
        logger.exception("Error deleting event %s", event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
