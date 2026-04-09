"""
Router: Member
──────────────
GET  /api/members          → REQ-MEMBER-001  (Admin only)
POST /api/members          → REQ-MEMBER-001  (Admin only)
PUT  /api/members/<id>     → REQ-MEMBER-001  (Admin only)
GET  /api/members/lookup   → Verifikasi member untuk UMKM (X-Member-Lookup-Key)

━━━ CHANGELOG ━━━
[NEW] GET /api/members/lookup
  Endpoint untuk aplikasi UMKM memverifikasi status member saat transaksi.
  Proteksi via header X-Member-Lookup-Key (shared secret antar tim Gate & UMKM).
  Lookup by nfc_uid ATAU no_hp. Tidak mengekspos data sensitif (hanya nama + status).
  Kompatibel dengan USB RFID Reader mode keyboard-emulator (UID masuk sebagai text).
  Konfigurasi: set MEMBER_LOOKUP_API_KEY di .env Gate dan GATE_LOOKUP_KEY di .env UMKM.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.config import config
from app.dependencies import CurrentUser, admin_only, supabase

router = APIRouter(prefix="/members", tags=["Members"])


# ── GET /members/lookup ───────────────────────────────────────────────────────
# HARUS DIDEFINISIKAN SEBELUM /{member_id} agar FastAPI tidak misparsing
# "lookup" sebagai UUID member_id.

@router.get("/lookup")
def lookup_member(
    uid: str = Query("", description="NFC UID dari kartu (hex string). Prioritas 1."),
    no_hp: str = Query("", description="Nomor HP member. Fallback jika tidak ada NFC reader."),
    x_member_lookup_key: Optional[str] = Header(None, alias="X-Member-Lookup-Key"),
):
    """
    Verifikasi status member untuk dipakai oleh aplikasi UMKM saat transaksi.

    CARA PAKAI:
      - Dengan NFC reader (USB keyboard emulator): scan kartu → uid terisi otomatis
      - Tanpa NFC reader: kasir UMKM input nomor HP member secara manual
      - Minimal satu dari uid atau no_hp harus diisi

    PROTEKSI:
      Header X-Member-Lookup-Key wajib diisi dengan shared secret yang sama
      antara Gate dan UMKM. Set MEMBER_LOOKUP_API_KEY di .env Gate Backend.
      Jika MEMBER_LOOKUP_API_KEY kosong (belum dikonfigurasi), endpoint DITOLAK.

    RESPONSE (data tidak ekspos email/nfc_uid/id lengkap untuk privasi):
      { status, data: { nama, status, is_aktif, no_hp_masked } }
    """
    # Validasi API key
    if not config.MEMBER_LOOKUP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": "Endpoint lookup belum dikonfigurasi. Set MEMBER_LOOKUP_API_KEY di Gate Backend.",
            },
        )

    if not x_member_lookup_key or x_member_lookup_key != config.MEMBER_LOOKUP_API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "API key tidak valid"},
        )

    # Minimal satu identifier harus ada
    uid_clean = uid.strip()
    no_hp_clean = no_hp.strip()

    if not uid_clean and not no_hp_clean:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Parameter uid (NFC UID) atau no_hp harus diisi",
            },
        )

    try:
        query = supabase.table("member").select("id, nama, no_hp, status")

        if uid_clean:
            # Prioritaskan lookup by UID NFC
            query = query.eq("nfc_uid", uid_clean)
        else:
            # Fallback: lookup by nomor HP
            query = query.eq("no_hp", no_hp_clean)

        res = query.maybe_single().execute()

        if not res or res.data is None:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Member tidak ditemukan dalam sistem"},
            )

        m = res.data

        # Masking no_hp untuk privasi: 08123****456
        no_hp_raw = m.get("no_hp", "")
        if len(no_hp_raw) > 6:
            no_hp_masked = no_hp_raw[:4] + "****" + no_hp_raw[-3:]
        else:
            no_hp_masked = no_hp_raw

        return {
            "status": "success",
            "data": {
                "nama": m["nama"],
                "status": m["status"],
                "is_aktif": m["status"] == "aktif",
                "no_hp_masked": no_hp_masked,
                "lookup_by": "uid" if uid_clean else "no_hp",
            },
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── GET /members ──────────────────────────────────────────────────────────────

@router.get("")
def get_members(
    status: str = Query(""),
    search: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    try:
        query = supabase.table("member").select("*").order("created_at", desc=True)

        if status in ("aktif", "nonaktif"):
            query = query.eq("status", status)

        s = search.strip()
        if s:
            query = query.or_(f"nama.ilike.%{s}%,no_hp.ilike.%{s}%")

        result = query.execute()
        return {"status": "success", "data": result.data}

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── POST /members ─────────────────────────────────────────────────────────────

class CreateMemberBody(BaseModel):
    nfc_uid: str
    nama: str
    no_hp: str
    status: Optional[str] = "aktif"          # default: aktif (server sets this)
    tanggal_daftar: Optional[str] = None      # default: hari ini (server sets this)
    email: Optional[str] = None


@router.post("", status_code=201)
def create_member(body: CreateMemberBody, _user: CurrentUser = Depends(admin_only)):
    if not body.nfc_uid or not body.nama or not body.no_hp:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Field nfc_uid, nama, dan no_hp wajib diisi",
            },
        )

    # Server menentukan nilai default — client tidak bisa salah input
    from datetime import date
    resolved_status = body.status if body.status in ("aktif", "nonaktif") else "aktif"
    resolved_tanggal = body.tanggal_daftar or date.today().isoformat()

    insert_payload = {
        "nfc_uid":        body.nfc_uid.strip(),
        "nama":           body.nama.strip(),
        "no_hp":          body.no_hp.strip(),
        "email":          body.email or None,
        "status":         resolved_status,
        "tanggal_daftar": resolved_tanggal,
    }

    try:
        result = supabase.table("member").insert(insert_payload).execute()
        return {
            "status": "success",
            "message": "Member berhasil didaftarkan",
            "data": result.data[0],
        }
    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "UID NFC sudah terdaftar dalam sistem"},
            )
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── PUT /members/<id> ─────────────────────────────────────────────────────────

class UpdateMemberBody(BaseModel):
    nfc_uid: Optional[str] = None
    nama: Optional[str] = None
    no_hp: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None


@router.put("/{member_id}")
def update_member(
    member_id: UUID,
    body: UpdateMemberBody,
    _user: CurrentUser = Depends(admin_only),
):
    update_payload = body.model_dump(exclude_none=True)

    if not update_payload:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
            },
        )

    if "status" in update_payload and update_payload["status"] not in ("aktif", "nonaktif"):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Format data tidak valid. Periksa kembali field yang dikirimkan",
            },
        )

    try:
        result = (
            supabase.table("member")
            .update(update_payload)
            .eq("id", str(member_id))
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Member tidak ditemukan"},
            )

        return {
            "status": "success",
            "message": "Data member berhasil diupdate",
            "data": result.data[0],
        }
    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(
                status_code=400,
                detail={"status": "error", "message": "UID NFC sudah digunakan oleh member lain"},
            )
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )