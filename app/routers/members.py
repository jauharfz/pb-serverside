"""
Router: Member
──────────────
GET  /api/members/lookup   → Verifikasi member untuk UMKM (X-Member-Lookup-Key)
GET  /api/members          → Admin only
POST /api/members          → Admin only
PUT  /api/members/{id}     → Admin only

CATATAN: /lookup HARUS didefinisikan sebelum /{member_id}
         agar FastAPI tidak misparsing "lookup" sebagai UUID.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from app.core.dependencies import CurrentUser, admin_only
from app.schemas.members import CreateMemberRequest, UpdateMemberRequest
from app.services import member_service

router = APIRouter(prefix="/members", tags=["Members"])


@router.get("/lookup")
def lookup_member(
    uid: str = Query("", description="NFC UID dari kartu. Prioritas 1."),
    no_hp: str = Query("", description="Nomor HP member. Fallback jika tidak ada NFC reader."),
    x_member_lookup_key: Optional[str] = Header(None, alias="X-Member-Lookup-Key"),
):
    return member_service.lookup_member(uid=uid, no_hp=no_hp, api_key=x_member_lookup_key)


@router.get("")
def list_members(
    status: str = Query(""),
    search: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    return member_service.list_members(member_status=status, search=search)


@router.post("", status_code=201)
def create_member(
    body: CreateMemberRequest,
    _user: CurrentUser = Depends(admin_only),
):
    return member_service.create_member(
        nfc_uid=body.nfc_uid,
        nama=body.nama,
        no_hp=body.no_hp,
        member_status=body.status,
        tanggal_daftar=body.tanggal_daftar,
        email=body.email,
    )


@router.put("/{member_id}")
def update_member(
    member_id: UUID,
    body: UpdateMemberRequest,
    _user: CurrentUser = Depends(admin_only),
):
    return member_service.update_member(
        member_id=member_id,
        payload=body.model_dump(exclude_none=True),
    )
