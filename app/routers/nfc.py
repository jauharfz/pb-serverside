"""
Router: NFC Tap
────────────────
POST /api/tap → REQ-NFC-001 s/d REQ-NFC-004

Endpoint ini TIDAK memerlukan JWT — dipanggil langsung
oleh NFC Reader via HTTP POST. Keamanan via HTTPS/TLS.
"""

from fastapi import APIRouter

from app.schemas.nfc import TapRequest
from app.services import nfc_service

router = APIRouter(tags=["NFC"])


@router.post("/tap")
def tap(body: TapRequest):
    return nfc_service.process_tap(uid=body.uid, reader_timestamp=body.timestamp)
