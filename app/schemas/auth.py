from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        return v.strip()


class UpdateNamaRequest(BaseModel):
    nama: str

    @field_validator("nama")
    @classmethod
    def nama_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nama tidak boleh kosong")
        return v


class UpdatePasswordRequest(BaseModel):
    password_lama: str
    password_baru: str
