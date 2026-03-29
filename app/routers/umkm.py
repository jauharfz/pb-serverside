"""
Router: Integrasi UMKM Eksternal
──────────────────────────────────
GET /api/umkm → REQ-INTEG-001  (Admin only)

FastAPI bertindak sebagai proxy ke API eksternal kelompok UMKM.
URL dan API key dikonfigurasi via environment variable:
  UMKM_API_URL  → endpoint API eksternal
  UMKM_API_KEY  → bearer token API eksternal (jika ada)
"""

import requests as http
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import config
from app.dependencies import CurrentUser, admin_only

router = APIRouter(prefix="/umkm", tags=["UMKM"])

_TIMEOUT = 10  # detik


@router.get("")
def get_umkm(
    kategori: str = Query(""),
    is_aktif: str = Query(""),
    _user: CurrentUser = Depends(admin_only),
):
    api_url = config.UMKM_API_URL.strip()
    api_key = config.UMKM_API_KEY.strip()

    if not api_url:
        return {
            "status": "success",
            "source": "external_umkm_api",
            "data": [],
            "_info": "UMKM_API_URL belum dikonfigurasi",
        }

    # ── Forward query params yang relevan ─────────────────────────────────
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

        # Normalisasi: API eksternal bisa mengembalikan list atau {"data": [...]}
        data = external if isinstance(external, list) else external.get("data", [])

        return {
            "status": "success",
            "source": "external_umkm_api",
            "data": data,
        }

    except (http.exceptions.Timeout, http.exceptions.HTTPError, Exception):
        raise HTTPException(
            status_code=502,
            detail={
                "status": "error",
                "message": "Gagal mengambil data dari API eksternal kelompok UMKM",
            },
        )
