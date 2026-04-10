import re
from typing import Optional

from pydantic import BaseModel, field_validator

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(v: str) -> str:
    v = v.strip()
    if not _DATE_RE.match(v):
        raise ValueError("Format tanggal tidak valid. Gunakan YYYY-MM-DD")
    return v


class CreateEventRequest(BaseModel):
    nama_event: str
    tanggal: str
    lokasi: str

    @field_validator("nama_event", "lokasi")
    @classmethod
    def strip_and_require(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field tidak boleh kosong")
        return v

    @field_validator("tanggal")
    @classmethod
    def validate_tanggal(cls, v: str) -> str:
        return _validate_date(v)


class PatchEventRequest(BaseModel):
    status: Optional[str] = None
    nama_event: Optional[str] = None
    lokasi: Optional[str] = None
    tanggal: Optional[str] = None
