"""
Router: Pengunjung
───────────────────
GET  /api/visitors         → Admin & Petugas (require_auth)
POST /api/visitors/manual  → Admin & Petugas (require_auth)

GET /visitors menggunakan PostgREST nested select untuk join tabel member
secara inline: select("*, member:member_id(nama)").
Response menyertakan objek nested { member: { nama: "..." } } atau member: null
untuk pengunjung biasa.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import CurrentUser, require_auth, supabase

router = APIRouter(prefix="/visitors", tags=["Visitors"])


# ── GET /visitors ─────────────────────────────────────────────────────────────

@router.get("")
def get_visitors(
    tanggal: str = Query(""),
    event_id: str = Query(""),
    tipe_pengunjung: str = Query(""),
    status: str = Query(""),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _user: CurrentUser = Depends(require_auth),
):
    try:
        query = (
            supabase.table("kunjungan")
            .select("*, member:member_id(nama)")
            .order("waktu_masuk", desc=True)
            .range(offset, offset + limit - 1)
        )

        if event_id:
            query = query.eq("event_id", event_id)
        if tipe_pengunjung in ("member", "biasa"):
            query = query.eq("tipe_pengunjung", tipe_pengunjung)
        if status in ("di_dalam", "keluar"):
            query = query.eq("status", status)
        if tanggal:
            query = (
                query
                .gte("waktu_masuk", f"{tanggal}T00:00:00+07:00")
                .lte("waktu_masuk", f"{tanggal}T23:59:59+07:00")
            )

        result = query.execute()
        return {"status": "success", "data": result.data}

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )


# ── POST /visitors/manual ─────────────────────────────────────────────────────

class ManualVisitorBody(BaseModel):
    aksi: str
    event_id: str


@router.post("/manual", status_code=201)
def manual_visitor(body: ManualVisitorBody, user: CurrentUser = Depends(require_auth)):
    aksi = body.aksi.strip()
    event_id = body.event_id.strip()

    if aksi not in ("masuk", "keluar"):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "message": "Field aksi harus berupa 'masuk' atau 'keluar'",
            },
        )

    if not event_id:
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Field aksi dan event_id wajib diisi"},
        )

    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        if aksi == "masuk":
            result = (
                supabase.table("kunjungan")
                .insert({
                    "event_id":        event_id,
                    "member_id":       None,
                    "tipe_pengunjung": "biasa",
                    "waktu_masuk":     now,
                    "waktu_keluar":    None,
                    "status":          "di_dalam",
                    "dicatat_oleh":    user.user_id,
                })
                .execute()
            )
            message = "Pengunjung biasa masuk berhasil dicatat"

        else:
            find_res = (
                supabase.table("kunjungan")
                .select("id")
                .eq("event_id", event_id)
                .eq("tipe_pengunjung", "biasa")
                .eq("status", "di_dalam")
                .order("waktu_masuk")
                .limit(1)
                .execute()
            )

            if not find_res.data:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status": "error",
                        "message": "Tidak ada pengunjung biasa yang sedang di dalam",
                    },
                )

            kunjungan_id = find_res.data[0]["id"]
            result = (
                supabase.table("kunjungan")
                .update({"waktu_keluar": now})
                .eq("id", kunjungan_id)
                .execute()
            )
            message = "Pengunjung biasa keluar berhasil dicatat"

        if not result.data:
            raise HTTPException(
                status_code=500,
                detail={"status": "error", "message": "Terjadi kesalahan pada server"},
            )

        return {
            "status": "success",
            "message": message,
            "data": result.data[0],
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )