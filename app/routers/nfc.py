"""
Router: NFC Tap (OPTIMIZED)
────────────────────────────
POST /api/tap  → REQ-NFC-001, REQ-NFC-002, REQ-NFC-003, REQ-NFC-004

Endpoint ini TIDAK memerlukan JWT karena dipanggil langsung
oleh NFC Reader 13.56 MHz melalui HTTP POST standar.
Keamanan dijamin via HTTPS/TLS.

OPTIMASI:
  - Cache module-level untuk event aktif dan admin_id
    → warm request hanya butuh 2 DB calls (validate + write)
  - Cache invalidation jika insert/update gagal

Cache TTL: 60 detik.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import supabase

router = APIRouter(tags=["NFC"])

# ── Module-level cache (per worker, reset saat restart) ───────────────────────
_CACHE_TTL = timedelta(seconds=60)

_CACHED_EVENT: dict | None = None       # {"id": "...", "nama_event": "..."}
_CACHED_EVENT_AT: datetime | None = None
_CACHED_ADMIN_ID: str | None = None


def _get_active_event() -> dict | None:
    """Ambil event aktif. Gunakan cache jika masih dalam TTL."""
    global _CACHED_EVENT, _CACHED_EVENT_AT
    now = datetime.now(tz=timezone.utc)
    if _CACHED_EVENT and _CACHED_EVENT_AT and (now - _CACHED_EVENT_AT) < _CACHE_TTL:
        return _CACHED_EVENT
    res = (
        supabase.table("event")
        .select("id, nama_event")
        .eq("status", "aktif")
        .limit(1)
        .execute()
    )
    if res.data:
        _CACHED_EVENT = res.data[0]
        _CACHED_EVENT_AT = now
    else:
        _CACHED_EVENT = None
        _CACHED_EVENT_AT = None
    return _CACHED_EVENT


def _get_admin_id() -> str | None:
    """Ambil admin ID pertama. Gunakan cache jika tersedia."""
    global _CACHED_ADMIN_ID
    if _CACHED_ADMIN_ID:
        return _CACHED_ADMIN_ID
    res = (
        supabase.table("admin")
        .select("id")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if res.data:
        _CACHED_ADMIN_ID = res.data[0]["id"]
    return _CACHED_ADMIN_ID


def _invalidate_event_cache():
    global _CACHED_EVENT, _CACHED_EVENT_AT
    _CACHED_EVENT = None
    _CACHED_EVENT_AT = None


# ── Tap Endpoint ──────────────────────────────────────────────────────────────

class TapBody(BaseModel):
    uid: str
    timestamp: Optional[str] = None  # opsional — advisory only, server selalu pakai NOW()


@router.post("/tap")
def tap(body: TapBody):
    uid = body.uid.strip()

    if not uid:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Field uid wajib diisi"},
        )

    # Server selalu pakai waktu server sebagai sumber truth
    server_now = datetime.now(tz=timezone.utc)
    waktu_masuk_iso = server_now.isoformat()

    # Simpan reader_timestamp untuk audit jika ada & selisih > 30 detik
    reader_ts_iso: str | None = None
    if body.timestamp:
        try:
            reader_ts = datetime.fromisoformat(body.timestamp.strip().replace("Z", "+00:00"))
            selisih_detik = abs((server_now - reader_ts).total_seconds())
            if selisih_detik > 30:
                reader_ts_iso = reader_ts.isoformat()  # log untuk audit
        except ValueError:
            pass  # timestamp tidak valid — abaikan, lanjut dengan server time

    try:
        # ── 1. Validasi UID via RPC (selalu fresh, tidak di-cache) ────────
        validate_res = supabase.rpc("fn_validate_nfc_uid", {"p_uid": uid}).execute()

        if not validate_res.data or not validate_res.data[0].get("is_valid"):
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "UID NFC tidak terdaftar dalam sistem"},
            )

        member = validate_res.data[0]
        member_id = member["member_id"]
        nama_member = member["nama"]
        is_inside = member.get("is_inside", False)

        # ── 2. Event aktif (dari cache) ───────────────────────────────────
        active_event = _get_active_event()
        if not active_event:
            raise HTTPException(
                status_code=404,
                detail={"status": "error", "message": "Tidak ada event aktif saat ini"},
            )
        event_id = active_event["id"]

        # ── 3. Admin ID (dari cache) ──────────────────────────────────────
        dicatat_oleh = _get_admin_id()
        if not dicatat_oleh:
            _invalidate_event_cache()
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                },
            )

        # ── 4. Tap masuk atau keluar ──────────────────────────────────────
        if not is_inside:
            insert_res = (
                supabase.table("kunjungan")
                .insert({
                    "event_id":        event_id,
                    "member_id":       member_id,
                    "tipe_pengunjung": "member",
                    "waktu_masuk":     waktu_masuk_iso,
                    "waktu_keluar":    None,
                    "status":          "di_dalam",
                    "dicatat_oleh":    dicatat_oleh,
                })
                .execute()
            )

            if not insert_res.data:
                _invalidate_event_cache()
                raise HTTPException(
                    status_code=500,
                    detail={
                        "status": "error",
                        "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                    },
                )

            k = insert_res.data[0]
            return {
                "status":  "success",
                "message": "Tap masuk berhasil dicatat",
                "data": {
                    "kunjungan_id": k["id"],
                    "event_id":     event_id,
                    "member_id":    member_id,
                    "nama_member":  nama_member,
                    "aksi":         "masuk",
                    "waktu_masuk":  k["waktu_masuk"],
                    "waktu_keluar": None,
                    "status":       "di_dalam",
                },
            }

        else:
            update_res = (
                supabase.table("kunjungan")
                .update({"waktu_keluar": waktu_masuk_iso, "status": "keluar"})
                .eq("member_id", member_id)
                .eq("event_id",  event_id)
                .eq("status",    "di_dalam")
                .execute()
            )

            if not update_res.data:
                _invalidate_event_cache()
                raise HTTPException(
                    status_code=500,
                    detail={
                        "status": "error",
                        "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
                    },
                )

            k = update_res.data[0]
            return {
                "status":  "success",
                "message": "Tap keluar berhasil dicatat",
                "data": {
                    "kunjungan_id": k["id"],
                    "event_id":     event_id,
                    "member_id":    member_id,
                    "nama_member":  nama_member,
                    "aksi":         "keluar",
                    "waktu_masuk":  k["waktu_masuk"],
                    "waktu_keluar": k["waktu_keluar"],
                    "status":       "keluar",
                },
            }

    except HTTPException:
        raise
    except Exception:
        _invalidate_event_cache()
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Gagal menyimpan data ke Supabase. Coba lagi beberapa saat.",
            },
        )