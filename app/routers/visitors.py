"""
Router: Pengunjung
───────────────────
GET  /api/visitors         → Admin & Petugas
POST /api/visitors/manual  → Admin & Petugas
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.core.dependencies import CurrentUser, require_auth
from app.schemas.visitors import ManualVisitorRequest
from app.services import visitor_service

router = APIRouter(prefix="/visitors", tags=["Visitors"])


@router.get("")
def list_visitors(
    tanggal: str = Query(""),
    event_id: str = Query(""),
    tipe_pengunjung: str = Query(""),
    visitor_status: str = Query("", alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _user: CurrentUser = Depends(require_auth),
):
    return visitor_service.list_visitors(
        tanggal=tanggal,
        event_id=event_id,
        tipe_pengunjung=tipe_pengunjung,
        visitor_status=visitor_status,
        limit=limit,
        offset=offset,
    )


@router.post("/manual", status_code=201)
def manual_visitor(
    body: ManualVisitorRequest,
    user: CurrentUser = Depends(require_auth),
):
    aksi = body.aksi.strip()
    event_id = body.event_id.strip()

    if aksi not in ("masuk", "keluar"):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Field aksi harus berupa 'masuk' atau 'keluar'"},
        )
    if not event_id:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"status": "error", "message": "Field aksi dan event_id wajib diisi"},
        )

    return visitor_service.manual_visitor(aksi=aksi, event_id=event_id, user_id=user.user_id)
