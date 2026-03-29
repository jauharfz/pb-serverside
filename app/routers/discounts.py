"""
Router: Diskon UMKM
────────────────────
GET /api/discounts → REQ-MEMBER-002  (Admin & Petugas)

Membaca tabel diskon_member + tenant_umkm (join via PostgREST nested select).
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import CurrentUser, require_auth, supabase

router = APIRouter(prefix="/discounts", tags=["Discounts"])


@router.get("")
def get_discounts(
    is_aktif: str = Query("true"),
    tenant_id: str = Query(""),
    _user: CurrentUser = Depends(require_auth),
):
    is_aktif_str = is_aktif.lower()

    try:
        query = (
            supabase.table("diskon_member")
            .select("*, tenant:tenant_umkm(*)")
            .order("berlaku_mulai", desc=True)
        )

        if is_aktif_str == "true":
            query = query.eq("is_aktif", True)
        elif is_aktif_str == "false":
            query = query.eq("is_aktif", False)

        if tenant_id:
            query = query.eq("tenant_id", tenant_id)

        result = query.execute()
        return {"status": "success", "data": result.data}

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Terjadi kesalahan pada server"},
        )
