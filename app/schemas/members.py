from typing import Optional

from pydantic import BaseModel


class CreateMemberRequest(BaseModel):
    nfc_uid: str
    nama: str
    no_hp: str
    status: Optional[str] = "aktif"
    tanggal_daftar: Optional[str] = None
    email: Optional[str] = None


class UpdateMemberRequest(BaseModel):
    nfc_uid: Optional[str] = None
    nama: Optional[str] = None
    no_hp: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
