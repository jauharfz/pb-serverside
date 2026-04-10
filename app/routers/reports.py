"""
Router: Laporan
────────────────
GET /api/reports         → REQ-REPORT-001 (Admin only)
GET /api/reports/export  → REQ-REPORT-002 (Admin only)
"""

import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import CurrentUser, admin_only
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("")
def get_reports(
    tanggal: str = Query(""),
    event_id: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    return report_service.get_reports(tanggal=tanggal, event_id=event_id)


@router.get("/export")
def export_report(
    format: str = Query(""),
    tanggal: str = Query(""),
    event_id: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    fmt = format.lower().strip()
    tanggal = tanggal.strip()
    event_id = event_id.strip()

    if fmt not in ("pdf", "excel"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Parameter format harus berupa 'pdf' atau 'excel'"},
        )

    if not event_id and not tanggal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Parameter event_id atau tanggal harus disertakan"},
        )

    if tanggal:
        try:
            datetime.strptime(tanggal, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Format tanggal tidak valid. Gunakan YYYY-MM-DD"},
            )

    data, filename, mime = report_service.export_report(fmt=fmt, tanggal=tanggal, event_id=event_id)

    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
