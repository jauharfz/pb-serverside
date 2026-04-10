"""
Router: Diskon UMKM
────────────────────
GET /api/discounts → REQ-MEMBER-002 (Admin & Petugas)
"""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import CurrentUser, require_auth
from app.services import umkm_service

router = APIRouter(prefix="/discounts", tags=["Discounts"])


@router.get("")
async def get_discounts(
    is_aktif: str = Query("true"),
    tenant_id: str = Query(""),
    _user: CurrentUser = Depends(require_auth),
):
    is_aktif_bool: bool | None = None
    if is_aktif.lower() == "true":
        is_aktif_bool = True
    elif is_aktif.lower() == "false":
        is_aktif_bool = False

    return await umkm_service.get_discounts(
        is_aktif_bool=is_aktif_bool,
        tenant_id=tenant_id.strip(),
    )
