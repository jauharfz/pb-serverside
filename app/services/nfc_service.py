"""
services/nfc_service.py
────────────────────────
Business logic untuk NFC tap (masuk/keluar).

Cache module-level untuk event aktif dan admin_id (TTL 60 detik per worker).
Endpoint ini TIDAK memerlukan JWT — dipanggil langsung oleh NFC reader via HTTP.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.db.client import get_supabase

logger = logging.getLogger(__name__)

_CACHE_TTL = timedelta(seconds=60)

_cached_event: Optional[dict] = None
_cached_event_at: Optional[datetime] = None
_cached_admin_id: Optional[str] = None


def _get_active_event() -> Optional[dict]:
    global _cached_event, _cached_event_at
    now = datetime.now(tz=timezone.utc)
    if _cached_event and _cached_event_at and (now - _cached_event_at) < _CACHE_TTL:
        return _cached_event

    supabase = get_supabase()
    res = (
        supabase.table("event")
        .select("id, nama_event")
        .eq("status", "aktif")
        .limit(1)
        .execute()
    )
    if res.data:
        _cached_event = res.data[0]
        _cached_event_at = now
    else:
        _cached_event = None
        _cached_event_at = None
    return _cached_event


def _get_admin_id() -> Optional[str]:
    global _cached_admin_id
    if _cached_admin_id:
        return _cached_admin_id

    supabase = get_supabase()
    res = (
        supabase.table("admin")
        .select("id")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if res.data:
        _cached_admin_id = res.data[0]["id"]
    return _cached_admin_id


def _invalidate_event_cache() -> None:
    global _cached_event, _cached_event_at
    _cached_event = None
    _cached_event_at = None


def process_tap(uid: str, reader_timestamp: Optional[str]) -> dict:
    """Proses NFC tap masuk/keluar."""
    uid = uid.strip()
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Field uid wajib diisi"},
        )

    supabase = get_supabase()
    server_now = datetime.now(tz=timezone.utc)
    waktu_masuk_iso = server_now.isoformat()

    # Audit jika selisih reader timestamp > 30 detik
    if reader_timestamp:
        try:
            reader_ts = datetime.fromisoformat(
                reader_timestamp.strip().replace("Z", "+00:00")
            )
            if abs((server_now - reader_ts).total_seconds()) > 30:
                logger.warning(
                    "Clock drift detected for uid=%s: server=%s reader=%s",
                    uid,
                    server_now.isoformat(),
                    reader_ts.isoformat(),
                )
        except ValueError:
            pass  # timestamp tidak valid — abaikan

    try:
        # 1. Validasi UID via RPC (selalu fresh)
        validate_res = supabase.rpc("fn_validate_nfc_uid", {"p_uid": uid}).execute()

        if not validate_res.data or not validate_res.data[0].get("is_valid"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "UID NFC tidak terdaftar dalam sistem"},
            )

        member = validate_res.data[0]
        member_id: str = member["member_id"]
        nama_member: str = member["nama"]
        is_inside: bool = member.get("is_inside", False)

        # 2. Event aktif (cache TTL 60s)
        active_event = _get_active_event()
        if not active_event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Tidak ada event aktif saat ini"},
            )
        event_id: str = active_event["id"]

        # 3. Admin ID (cached, no expiry — jarang berubah)
        dicatat_oleh = _get_admin_id()
        if not dicatat_oleh:
            _invalidate_event_cache()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "status": "error",
                    "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                },
            )

        # 4. Tap masuk atau keluar
        if not is_inside:
            return _tap_masuk(supabase, event_id, member_id, nama_member, dicatat_oleh, waktu_masuk_iso)

        return _tap_keluar(supabase, event_id, member_id, nama_member, waktu_masuk_iso)

    except HTTPException:
        raise
    except Exception:
        _invalidate_event_cache()
        logger.exception("Unexpected error processing tap for uid=%s", uid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
            },
        )


def _tap_masuk(
    supabase,
    event_id: str,
    member_id: str,
    nama_member: str,
    dicatat_oleh: str,
    waktu_masuk_iso: str,
) -> dict:
    insert_res = (
        supabase.table("kunjungan")
        .insert({
            "event_id": event_id,
            "member_id": member_id,
            "tipe_pengunjung": "member",
            "waktu_masuk": waktu_masuk_iso,
            "waktu_keluar": None,
            "status": "di_dalam",
            "dicatat_oleh": dicatat_oleh,
        })
        .execute()
    )

    if not insert_res.data:
        _invalidate_event_cache()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
            },
        )

    k = insert_res.data[0]
    return {
        "status": "success",
        "message": "Tap masuk berhasil dicatat",
        "data": {
            "kunjungan_id": k["id"],
            "event_id": event_id,
            "member_id": member_id,
            "nama_member": nama_member,
            "aksi": "masuk",
            "waktu_masuk": k["waktu_masuk"],
            "waktu_keluar": None,
            "status": "di_dalam",
        },
    }


def _tap_keluar(
    supabase,
    event_id: str,
    member_id: str,
    nama_member: str,
    waktu_keluar_iso: str,
) -> dict:
    update_res = (
        supabase.table("kunjungan")
        .update({"waktu_keluar": waktu_keluar_iso, "status": "keluar"})
        .eq("member_id", member_id)
        .eq("event_id", event_id)
        .eq("status", "di_dalam")
        .execute()
    )

    if not update_res.data:
        _invalidate_event_cache()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
            },
        )

    k = update_res.data[0]
    return {
        "status": "success",
        "message": "Tap keluar berhasil dicatat",
        "data": {
            "kunjungan_id": k["id"],
            "event_id": event_id,
            "member_id": member_id,
            "nama_member": nama_member,
            "aksi": "keluar",
            "waktu_masuk": k["waktu_masuk"],
            "waktu_keluar": k["waktu_keluar"],
            "status": "keluar",
        },
    }
