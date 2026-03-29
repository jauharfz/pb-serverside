"""
Router: Member
──────────────
GET  /api/members       → REQ-MEMBER-001  (Admin only)
POST /api/members       → REQ-MEMBER-001  (Admin only)
PUT  /api/members/<id>  → REQ-MEMBER-001  (Admin only)
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import CurrentUser, admin_only, supabase

router = APIRouter(prefix="/members", tags=["Members"])


# ── GET /members ──────────────────────────────────────────────────────────────

@router.get("")
def get_members(
    status: str = Query(""),
    search: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    try:
        query = supabase.table("member").select("*").order("created_at", desc=True)

        if status in ("aktif", "nonaktif"):
            query = query.eq("status", status)

        s = search.strip()
        if s:
            query = query.or_(f"nama.ilike.%{s}%,no_hp.ilike.%{s}%")

        result = query.execute()
        return {"status": "success", "data": result.data}

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── POST /members ─────────────────────────────────────────────────────────────

class CreateMemberBody(BaseModel):
    nfc_uid: str
    nama: str
    no_hp: str
    status: str
    tanggal_daftar: str
    email: Optional[str] = None


@router.post("", status_code=201)
def create_member(body: CreateMemberBody, _user: CurrentUser = Depends(admin_only)):
    if not body.nfc_uid or not body.nama or not body.no_hp or not body.status or not body.tanggal_daftar:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Field nfc_uid, nama, no_hp, status, dan tanggal_daftar wajib diisi",
            },
        )

    if body.status not in ("aktif", "nonaktif"):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
            },
        )

    insert_payload = {
        "nfc_uid":        body.nfc_uid.strip(),
        "nama":           body.nama.strip(),
        "no_hp":          body.no_hp.strip(),
        "email":          body.email or None,
        "status":         body.status,
        "tanggal_daftar": body.tanggal_daftar,
    }

    try:
        result = supabase.table("member").insert(insert_payload).execute()
        return {
            "status": "success",
            "message": "Member berhasil didaftarkan",
            "data": result.data[0],
        }
    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "UID NFC sudah terdaftar dalam sistem"},
            )
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── PUT /members/<id> ─────────────────────────────────────────────────────────

class UpdateMemberBody(BaseModel):
    nfc_uid: Optional[str] = None
    nama: Optional[str] = None
    no_hp: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None


@router.put("/{member_id}")
def update_member(
    member_id: UUID,
    body: UpdateMemberBody,
    _user: CurrentUser = Depends(admin_only),
):
    update_payload = body.model_dump(exclude_none=True)

    if not update_payload:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
            },
        )

    if "status" in update_payload and update_payload["status"] not in ("aktif", "nonaktif"):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
            },
        )

    try:
        result = (
            supabase.table("member")
            .update(update_payload)
            .eq("id", str(member_id))
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
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
                status_code=400,
                detail={"status": "error", "message": "UID NFC sudah digunakan oleh member lain"},
            )
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
