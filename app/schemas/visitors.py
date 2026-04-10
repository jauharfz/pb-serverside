from pydantic import BaseModel


class ManualVisitorRequest(BaseModel):
    aksi: str
    event_id: str
