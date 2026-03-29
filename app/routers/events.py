"""
Router: Event Management
─────────────────────────
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
     - Jika edit tanggal → masa depan/lampau: status otomatis jadi 'selesai'

  [DELETE]
  - Event aktif tidak bisa dihapus
  - Event dengan kunjungan tidak bisa dihapus (FK RESTRICT dari Supabase)

  Invariant: hanya satu event 'aktif' di satu waktu.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies import CurrentUser, admin_only, supabase

router = APIRouter(prefix="/events", tags=["Events"])

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _today() -> str:
    """Tanggal hari ini WIB (UTC+7), format YYYY-MM-DD."""
    wib = datetime.utcnow() + timedelta(hours=7)
    return wib.strftime("%Y-%m-%d")


def _deactivate_other_events(exclude_id: str | None = None):
    """Nonaktifkan semua event aktif kecuali exclude_id."""
    query = (
        supabase.table("event")
        .update({"status": "selesai"})
        .eq("status", "aktif")
    )
    if exclude_id:
        query = query.neq("id", exclude_id)
    query.execute()


# ── GET /events ───────────────────────────────────────────────────────────────

@router.get("")
def get_events(_user: CurrentUser = Depends(admin_only)):
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
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── POST /events ──────────────────────────────────────────────────────────────

class CreateEventBody(BaseModel):
    nama_event: str
    tanggal: str
    lokasi: str


@router.post("", status_code=201)
def create_event(body: CreateEventBody, _user: CurrentUser = Depends(admin_only)):
    nama_event = body.nama_event.strip()
    tanggal    = body.tanggal.strip()
    lokasi     = body.lokasi.strip()

    if not nama_event or not tanggal or not lokasi:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Field nama_event, tanggal (YYYY-MM-DD), dan lokasi wajib diisi",
            },
        )

    if not _DATE_RE.match(tanggal):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD",
            },
        )

    today       = _today()
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
        return {
            "status":  "success",
            "message": "Event berhasil dibuat",
            "data":    created,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── PATCH /events/<id> ────────────────────────────────────────────────────────

class PatchEventBody(BaseModel):
    status: Optional[str] = None
    nama_event: Optional[str] = None
    lokasi: Optional[str] = None
    tanggal: Optional[str] = None


@router.patch("/{event_id}")
def update_event(
    event_id: str,
    body: PatchEventBody,
    _user: CurrentUser = Depends(admin_only),
):
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
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Event tidak ditemukan"},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )

    current = check.data

    if body.status is not None:
        return _handle_toggle_status(event_id, body.status, current)
    else:
        return _handle_edit_fields(event_id, body, current)


def _handle_toggle_status(event_id: str, new_status: str, current: dict):
    new_status = new_status.strip()

    if new_status not in ("aktif", "selesai"):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Nilai status tidak valid. Gunakan 'aktif' atau 'selesai'",
            },
        )

    # Guard: event masa depan tidak boleh diaktifkan
    if new_status == "aktif" and current["tanggal"] > _today():
        raise HTTPException(
            status_code=422,
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
            "status":  "success",
            "message": f"Status event berhasil diubah menjadi {new_status}",
            "data":    updated,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def _handle_edit_fields(event_id: str, body: PatchEventBody, current: dict):
    ALLOWED = {"nama_event", "lokasi", "tanggal"}
    payload = {
        k: v
        for k, v in body.model_dump(exclude_none=True).items()
        if k in ALLOWED
    }

    if not payload:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Tidak ada field yang valid untuk diperbarui"},
        )

    # Guard: tanggal tidak boleh diubah jika event sedang aktif
    if "tanggal" in payload and current["status"] == "aktif":
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Tanggal tidak dapat diubah saat event sedang aktif. Nonaktifkan event terlebih dahulu.",
            },
        )

    if "tanggal" in payload and not _DATE_RE.match(payload["tanggal"]):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD",
            },
        )

    today = _today()
    if "tanggal" in payload:
        new_tanggal     = payload["tanggal"]
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
        return {
            "status":  "success",
            "message": "Data event berhasil diperbarui",
            "data":    updated,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── DELETE /events/<id> ───────────────────────────────────────────────────────

@router.delete("/{event_id}")
def delete_event(event_id: str, _user: CurrentUser = Depends(admin_only)):
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
                status_code=404,
                detail={"status": "error", "message": "Event tidak ditemukan"},
            )

        if check.data.get("status") == "aktif":
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "error",
                    "message": "Event yang sedang aktif tidak dapat dihapus. Nonaktifkan terlebih dahulu.",
                },
            )

        result = (
            supabase.table("event")
            .delete()
            .eq("id", event_id)
            .execute()
        )

        if result.data is not None and len(result.data) == 0:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Event tidak ditemukan"},
            )

        return {"status": "success", "message": "Event berhasil dihapus"}

    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "foreign key" in msg or "restrict" in msg or "kunjungan" in msg:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "error",
                    "message": "Event tidak dapat dihapus karena sudah memiliki data kunjungan.",
                },
            )
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
