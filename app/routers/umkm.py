"""
Router: Integrasi UMKM Eksternal
──────────────────────────────────
GET /api/umkm → REQ-INTEG-001  (Admin only)

FastAPI bertindak sebagai proxy ke API eksternal kelompok UMKM.
URL dan API key dikonfigurasi via environment variable:
  UMKM_API_URL  → endpoint API eksternal
  UMKM_API_KEY  → bearer token API eksternal (jika ada)
  UMKM_USE_MOCK → jika "true", gunakan data mock (untuk dev/staging)
"""

import requests as http
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import config
from app.dependencies import CurrentUser, admin_only

router = APIRouter(prefix="/umkm", tags=["UMKM"])

_TIMEOUT = 10

_MOCK_DATA = [
    {"id": "aaa00001-0000-0000-0000-000000000001", "nama_tenant": "Warung Bu Sari",        "kategori": "Makanan", "nomor_stand": "A01", "deskripsi": "Nasi liwet dan lauk-pauk khas Banyumas"},
    {"id": "aaa00001-0000-0000-0000-000000000002", "nama_tenant": "Dawet Ireng Pak Gito",  "kategori": "Minuman", "nomor_stand": "A02", "deskripsi": "Dawet ireng legendaris sejak 1990"},
    {"id": "aaa00001-0000-0000-0000-000000000003", "nama_tenant": "Batik Banyumas Asri",   "kategori": "Fashion", "nomor_stand": "B01", "deskripsi": "Batik tulis motif sekar jagad khas Banyumas"},
    {"id": "aaa00001-0000-0000-0000-000000000004", "nama_tenant": "Getuk Goreng Sokaraja", "kategori": "Makanan", "nomor_stand": "B02", "deskripsi": "Getuk goreng original Sokaraja"},
    {"id": "aaa00001-0000-0000-0000-000000000005", "nama_tenant": "Kopi Robusta Merden",   "kategori": "Minuman", "nomor_stand": "C01", "deskripsi": "Single origin robusta dari lereng Slamet"},
    {"id": "aaa00001-0000-0000-0000-000000000006", "nama_tenant": "Kriya Bambu Lestari",   "kategori": "Kriya",   "nomor_stand": "C02", "deskripsi": "Kerajinan bambu anyam dan ukir"},
]


@router.get("")
def get_umkm(
    kategori: str = Query(""),
    is_aktif: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    # ── MOCK MODE ──────────────────────────────────────────────────────────
    if getattr(config, "UMKM_USE_MOCK", False):
        data = _MOCK_DATA
        if kategori:
            data = [d for d in data if d["kategori"] == kategori]
        return {"status": "success", "source": "mock", "data": data}
    # ───────────────────────────────────────────────────────────────────────

    api_url = config.UMKM_API_URL.strip()
    api_key = config.UMKM_API_KEY.strip()

    if not api_url:
        return {
            "status": "success",
            "source": "external_umkm_api",
            "data": [],
            "_info": "UMKM_API_URL belum dikonfigurasi",
        }

    params: dict = {}
    if kategori:
        params["kategori"] = kategori
    if is_aktif:
        params["is_aktif"] = is_aktif

    headers: dict = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = http.get(api_url, params=params, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        external = resp.json()
        data = external if isinstance(external, list) else external.get("data", [])
        return {"status": "success", "source": "external_umkm_api", "data": data}

    except (http.exceptions.Timeout, http.exceptions.HTTPError, Exception):
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "message": "Gagal mengambil data dari API eksternal kelompok UMKM"},
        )