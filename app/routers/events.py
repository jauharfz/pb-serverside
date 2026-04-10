"""
Router: Event Management
─────────────────────────
GET    /api/events/public  → publik (tanpa auth)
GET    /api/events         → Admin only
POST   /api/events         → Admin only
PATCH  /api/events/{id}    → Admin only
DELETE /api/events/{id}    → Admin only
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUser, admin_only
from app.schemas.events import CreateEventRequest, PatchEventRequest
from app.services import event_service

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/public")
def get_public_event():
    return event_service.get_public_event()


@router.get("")
def list_events(_user: CurrentUser = Depends(admin_only)):
    return event_service.list_events()


@router.post("", status_code=201)
def create_event(
    body: CreateEventRequest,
    _user: CurrentUser = Depends(admin_only),
):
    return event_service.create_event(
        nama_event=body.nama_event,
        tanggal=body.tanggal,
        lokasi=body.lokasi,
    )


@router.patch("/{event_id}")
def patch_event(
    event_id: str,
    body: PatchEventRequest,
    _user: CurrentUser = Depends(admin_only),
):
    return event_service.patch_event(event_id=event_id, body=body)


@router.delete("/{event_id}")
def delete_event(
    event_id: str,
    _user: CurrentUser = Depends(admin_only),
):
    return event_service.delete_event(event_id=event_id)
