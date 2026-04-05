"""
Router: Diskon UMKM (Integration v2)
──────────────────────────────────────
GET /api/discounts → REQ-MEMBER-002  (Admin & Petugas)

Dua mode dikontrol via env var UMKM_USE_MOCK:
  UMKM_USE_MOCK=true  → kembalikan data dummy statis (default saat dev/staging).
  UMKM_USE_MOCK=false → proxy ke UMKM Backend GET /api/public/diskon.

Perubahan dari versi sebelumnya:
  SEBELUM: membaca tabel diskon_member di Supabase Gate (tidak pernah diisi).
  SESUDAH: data diskon bersumber dari UMKM Backend via endpoint publik.

Format response tetap kompatibel dengan Gate Frontend (Tenants.jsx):
  { status, data: [ { id, tenant_id, nama_tenant, nomor_stand,
                       deskripsi_diskon, persentase_diskon,
                       berlaku_mulai, berlaku_hingga, is_aktif }, ... ] }
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import config
from app.dependencies import CurrentUser, require_auth

router = APIRouter(prefix="/discounts", tags=["Discounts"])

_TIMEOUT = 10  # detik

# ── Data mock untuk dev / staging ─────────────────────────────────────────────
_MOCK_DISCOUNTS = [
    {
        "id": "mock-disc-001",
        "tenant_id": "mock-tenant-001",
        "nama_tenant": "Sate Blengong Bu Yati",
        "nomor_stand": "A-12",
        "deskripsi_diskon": "Diskon 20% untuk member NFC",
        "persentase_diskon": 20.0,
        "berlaku_mulai": "2026-03-22",
        "berlaku_hingga": "2026-03-24",
        "is_aktif": True,
    },
    {
        "id": "mock-disc-002",
        "tenant_id": "mock-tenant-002",
        "nama_tenant": "Batik Ngapak Pak Darmo",
        "nomor_stand": "B-03",
        "deskripsi_diskon": "Gratis goodie bag untuk member",
        "persentase_diskon": 0.0,
        "berlaku_mulai": "2026-03-22",
        "berlaku_hingga": "2026-03-24",
        "is_aktif": True,
    },
    {
        "id": "mock-disc-003",
        "tenant_id": "mock-tenant-003",
        "nama_tenant": "Keripik Tempe Mak Jum",
        "nomor_stand": "A-05",
        "deskripsi_diskon": "Beli 2 gratis 1 untuk member NFC",
        "persentase_diskon": 0.0,
        "berlaku_mulai": "2026-03-22",
        "berlaku_hingga": "2026-03-24",
        "is_aktif": True,
    },
    {
        "id": "mock-disc-004",
        "tenant_id": "mock-tenant-005",
        "nama_tenant": "Es Dawet Ayu Bu Parti",
        "nomor_stand": "A-08",
        "deskripsi_diskon": "Diskon 15% untuk member NFC",
        "persentase_diskon": 15.0,
        "berlaku_mulai": "2026-03-22",
        "berlaku_hingga": "2026-03-24",
        "is_aktif": True,
    },
]


# ── GET /discounts ─────────────────────────────────────────────────────────────

@router.get("")
async def get_discounts(
    is_aktif: str = Query("true"),
    tenant_id: str = Query(""),
    _user: CurrentUser = Depends(require_auth),
):
    is_aktif_bool: bool | None = None
    if is_aktif.lower() == "true":
        is_aktif_bool = True
    elif is_aktif.lower() == "false":
        is_aktif_bool = False

    # ── Mode mock ─────────────────────────────────────────────────────────────
    if config.UMKM_USE_MOCK:
        data = list(_MOCK_DISCOUNTS)

        if tenant_id:
            data = [d for d in data if d["tenant_id"] == tenant_id]

        if is_aktif_bool is True:
            data = [d for d in data if d["is_aktif"]]
        elif is_aktif_bool is False:
            data = [d for d in data if not d["is_aktif"]]

        return {"status": "success", "data": data}

    # ── Mode live: proxy ke UMKM Backend ────────────────────────────────────
    api_base = (config.UMKM_API_BASE_URL or config.UMKM_API_URL).strip()

    if not api_base:
        return {"status": "success", "data": []}

    diskon_url = f"{api_base.rstrip('/')}/api/public/diskon"

    params: dict = {}
    if tenant_id:
        params["tenant_id"] = tenant_id
    if is_aktif_bool is not None:
        params["is_aktif"] = is_aktif_bool  # FastAPI UMKM menerima bool

    headers: dict = {"Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as _client:
            resp = await _client.get(diskon_url, params=params, headers=headers)
        resp.raise_for_status()
        external = resp.json()
        data = (
            external.get("data", [])
            if isinstance(external, dict)
            else external
        )
        return {"status": "success", "data": data}

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "status": "error",
                "message": "Timeout saat menghubungi API UMKM.",
            },
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "status": "error",
                "message": "Gagal mengambil data diskon dari API eksternal kelompok UMKM.",
            },
        )