"""
Router: Dashboard Stats
────────────────────────
GET /api/dashboard/stats → REQ-DASH-001 s/d REQ-DASH-004
"""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import CurrentUser, require_auth
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_stats(
    tanggal: str = Query(""),
    event_id: str = Query(""),
    _user: CurrentUser = Depends(require_auth),
):
    return dashboard_service.get_stats(tanggal=tanggal, event_id=event_id)
