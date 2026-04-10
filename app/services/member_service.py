"""
services/member_service.py
───────────────────────────
Business logic untuk manajemen member.
"""

import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.client import get_supabase

logger = logging.getLogger(__name__)


def lookup_member(uid: str, no_hp: str, api_key: Optional[str]) -> dict:
    """Verifikasi status member untuk aplikasi UMKM."""
    if not settings.MEMBER_LOOKUP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "message": "Endpoint lookup belum dikonfigurasi. Set MEMBER_LOOKUP_API_KEY di Gate Backend.",
            },
        )

    if not api_key or api_key != settings.MEMBER_LOOKUP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "message": "API key tidak valid"},
        )

    uid_clean = uid.strip()
    no_hp_clean = no_hp.strip()

    if not uid_clean and not no_hp_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": "Parameter uid (NFC UID) atau no_hp harus diisi",
            },
        )

    supabase = get_supabase()
    try:
        query = supabase.table("member").select("id, nama, no_hp, status")
        query = query.eq("nfc_uid", uid_clean) if uid_clean else query.eq("no_hp", no_hp_clean)
        res = query.maybe_single().execute()

        if not res or res.data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Member tidak ditemukan dalam sistem"},
            )

        m = res.data
        no_hp_raw = m.get("no_hp", "")
        no_hp_masked = (no_hp_raw[:4] + "****" + no_hp_raw[-3:]) if len(no_hp_raw) > 6 else no_hp_raw

        return {
            "status": "success",
            "data": {
                "nama": m["nama"],
                "status": m["status"],
                "is_aktif": m["status"] == "aktif",
                "no_hp_masked": no_hp_masked,
                "lookup_by": "uid" if uid_clean else "no_hp",
            },
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error looking up member uid=%s", uid_clean)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def list_members(member_status: str, search: str) -> dict:
    supabase = get_supabase()
    try:
        query = supabase.table("member").select("*").order("created_at", desc=True)
        if member_status in ("aktif", "nonaktif"):
            query = query.eq("status", member_status)
        s = search.strip()
        if s:
            query = query.or_(f"nama.ilike.%{s}%,no_hp.ilike.%{s}%")
        result = query.execute()
        return {"status": "success", "data": result.data}
    except Exception:
        logger.exception("Error listing members")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def create_member(
    nfc_uid: str,
    nama: str,
    no_hp: str,
    member_status: Optional[str],
    tanggal_daftar: Optional[str],
    email: Optional[str],
) -> dict:
    if not nfc_uid or not nama or not no_hp:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Field nfc_uid, nama, dan no_hp wajib diisi"},
        )

    resolved_status = member_status if member_status in ("aktif", "nonaktif") else "aktif"
    resolved_tanggal = tanggal_daftar or date.today().isoformat()

    supabase = get_supabase()
    try:
        result = (
            supabase.table("member")
            .insert({
                "nfc_uid": nfc_uid.strip(),
                "nama": nama.strip(),
                "no_hp": no_hp.strip(),
                "email": email or None,
                "status": resolved_status,
                "tanggal_daftar": resolved_tanggal,
            })
            .execute()
        )
        return {
            "status": "success",
            "message": "Member berhasil didaftarkan",
            "data": result.data[0],
        }
    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "UID NFC sudah terdaftar dalam sistem"},
            )
        logger.exception("Error creating member uid=%s", nfc_uid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


def update_member(member_id: UUID, payload: dict) -> dict:
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
            },
        )

    if "status" in payload and payload["status"] not in ("aktif", "nonaktif"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
            },
        )

    supabase = get_supabase()
    try:
        result = (
            supabase.table("member")
            .update(payload)
            .eq("id", str(member_id))
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Member tidak ditemukan"},
            )
        return {
            "status": "success",
            "message": "Data member berhasil diupdate",
            "data": result.data[0],
        }
    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "UID NFC sudah digunakan oleh member lain"},
            )
        logger.exception("Error updating member %s", member_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
