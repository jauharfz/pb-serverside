"""
Router: Integrasi UMKM Eksternal
──────────────────────────────────
GET   /api/umkm                          → REQ-INTEG-001 (Admin only)
GET   /api/umkm/registrations            → List pendaftaran (Admin only)
PATCH /api/umkm/registrations/{umkm_id}  → Approve/reject (Admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.core.dependencies import CurrentUser, admin_only
from app.services import umkm_service

router = APIRouter(prefix="/umkm", tags=["UMKM"])


@router.get("")
async def get_umkm(
    kategori: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    return await umkm_service.get_tenants(kategori=kategori.strip())


@router.get("/registrations")
async def get_registrations(
    reg_status: str = Query("", alias="status", description="Filter: pending | approved | rejected | (kosong = semua)"),
    _user: CurrentUser = Depends(admin_only),
):
    return await umkm_service.get_registrations(reg_status=reg_status.strip())


@router.patch("/registrations/{umkm_id}")
async def patch_registration(
    umkm_id: str,
    body: dict,
    _user: CurrentUser = Depends(admin_only),
):
    new_status = (body.get("status") or "").strip()
    if new_status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Status harus 'approved' atau 'rejected'."},
        )
    return await umkm_service.patch_registration(umkm_id=umkm_id, new_status=new_status)
