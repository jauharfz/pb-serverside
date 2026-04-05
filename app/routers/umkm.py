"""
Router: Integrasi UMKM Eksternal
──────────────────────────────────
GET /api/umkm → REQ-INTEG-001  (Admin only)

Dua mode operasi dikontrol via env var UMKM_USE_MOCK:
  UMKM_USE_MOCK=true  → kembalikan data dummy statis (default saat dev/staging).
  UMKM_USE_MOCK=false → proxy ke UMKM Backend GET /api/public/tenant.

URL UMKM Backend dikonfigurasi via:
  UMKM_API_BASE_URL → base URL, misal https://jauharfz-umkm-serverside.hf.space
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import config
from app.dependencies import CurrentUser, admin_only

router = APIRouter(prefix="/umkm", tags=["UMKM"])

_TIMEOUT = 10  # detik

# ── Data mock untuk dev / staging ─────────────────────────────────────────────
_MOCK_TENANTS = [
    {
        "id": "mock-tenant-001",
        "nama_tenant": "Sate Blengong Bu Yati",
        "kategori": "kuliner",
        "nomor_stand": "A-12",
        "deskripsi": "Sate Blengong khas Banyumas dengan bumbu rahasia turun-temurun.",
        "created_at": "2026-03-01T00:00:00+07:00",
    },
    {
        "id": "mock-tenant-002",
        "nama_tenant": "Batik Ngapak Pak Darmo",
        "kategori": "fashion",
        "nomor_stand": "B-03",
        "deskripsi": "Koleksi batik motif khas Banyumas dengan teknik tulis tangan.",
        "created_at": "2026-03-01T00:00:00+07:00",
    },
    {
        "id": "mock-tenant-003",
        "nama_tenant": "Keripik Tempe Mak Jum",
        "kategori": "kuliner",
        "nomor_stand": "A-05",
        "deskripsi": "Keripik tempe renyah aneka rasa, produksi rumahan Banyumas.",
        "created_at": "2026-03-01T00:00:00+07:00",
    },
    {
        "id": "mock-tenant-004",
        "nama_tenant": "Anyaman Bambu Pak Slamet",
        "kategori": "kerajinan",
        "nomor_stand": "C-02",
        "deskripsi": "Kerajinan anyaman bambu tradisional — tas, tudung saji, tikar.",
        "created_at": "2026-03-01T00:00:00+07:00",
    },
    {
        "id": "mock-tenant-005",
        "nama_tenant": "Es Dawet Ayu Bu Parti",
        "kategori": "minuman",
        "nomor_stand": "A-08",
        "deskripsi": "Es dawet ayu segar dengan santan murni dan gula aren asli.",
        "created_at": "2026-03-01T00:00:00+07:00",
    },
]


# ── GET /umkm ──────────────────────────────────────────────────────────────────

@router.get("")
async def get_umkm(
    kategori: str = Query(""),
    is_aktif: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    # ── Mode mock ─────────────────────────────────────────────────────────────
    if config.UMKM_USE_MOCK:
        data = list(_MOCK_TENANTS)
        if kategori:
            data = [t for t in data if kategori.lower() in t["kategori"].lower()]
        return {
            "status": "success",
            "source": "mock",
            "data": data,
            "_info": "Data mock — set UMKM_USE_MOCK=false untuk data nyata dari API UMKM.",
        }

    # ── Mode live: proxy ke UMKM Backend ────────────────────────────────────
    # Prioritaskan UMKM_API_BASE_URL; fallback ke UMKM_API_URL lama (deprecated).
    api_base = (config.UMKM_API_BASE_URL or config.UMKM_API_URL).strip()

    if not api_base:
        return {
            "status": "success",
            "source": "external_umkm_api",
            "data": [],
            "_info": "UMKM_API_BASE_URL belum dikonfigurasi.",
        }

    # Endpoint publik UMKM Backend — tidak memerlukan auth
    tenant_url = f"{api_base.rstrip('/')}/api/public/tenant"

    params: dict = {}
    if kategori:
        params["kategori"] = kategori
    # is_aktif tidak diforward ke /public/tenant karena endpoint tersebut
    # selalu hanya mengembalikan UMKM berstatus approved.

    headers: dict = {"Accept": "application/json"}
    # UMKM_API_KEY sudah tidak diperlukan untuk public endpoint,
    # tapi tetap dikirim jika dikonfigurasi (forward compat).
    if config.UMKM_API_KEY:
        headers["Authorization"] = f"Bearer {config.UMKM_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as _client:
            resp = await _client.get(tenant_url, params=params, headers=headers)
        resp.raise_for_status()
        external = resp.json()

        # UMKM Backend mengembalikan { status, data: [...] }
        data = (
            external.get("data", [])
            if isinstance(external, dict)
            else external
        )

        return {
            "status": "success",
            "source": "external_umkm_api",
            "data": data,
        }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "status": "error",
                "message": "Timeout saat menghubungi API UMKM. Coba lagi beberapa saat.",
            },
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={
                "status": "error",
                "message": "Gagal mengambil data dari API eksternal kelompok UMKM.",
            },
        )