from typing import Optional

from pydantic import BaseModel


class TapRequest(BaseModel):
    uid: str
    timestamp: Optional[str] = None  # advisory only — server selalu pakai NOW()
