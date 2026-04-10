"""
services/umkm_service.py
─────────────────────────
Business logic untuk integrasi UMKM eksternal.
Mode dikontrol via env var UMKM_USE_MOCK.
"""

import logging

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 10

_MOCK_TENANTS: list[dict] = [
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

_MOCK_DISCOUNTS: list[dict] = [
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


def _get_umkm_base() -> str:
    return (settings.UMKM_API_BASE_URL or settings.UMKM_API_URL).strip().rstrip("/")


def _admin_headers() -> dict:
    headers: dict = {"Accept": "application/json"}
    if settings.UMKM_ADMIN_SECRET_KEY:
        headers["X-Admin-Key"] = settings.UMKM_ADMIN_SECRET_KEY
    return headers


async def get_tenants(kategori: str) -> dict:
    if settings.UMKM_USE_MOCK:
        data = list(_MOCK_TENANTS)
        if kategori:
            data = [t for t in data if kategori.lower() in t["kategori"].lower()]
        return {
            "status": "success",
            "source": "mock",
            "data": data,
            "_info": "Data mock — set UMKM_USE_MOCK=false untuk data nyata dari API UMKM.",
        }

    api_base = _get_umkm_base()
    if not api_base:
        return {
            "status": "success",
            "source": "external_umkm_api",
            "data": [],
            "_info": "UMKM_API_BASE_URL belum dikonfigurasi.",
        }

    params: dict = {}
    if kategori:
        params["kategori"] = kategori

    headers: dict = {"Accept": "application/json"}
    if settings.UMKM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.UMKM_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{api_base}/api/public/tenant", params=params, headers=headers)
        resp.raise_for_status()
        external = resp.json()
        data = external.get("data", []) if isinstance(external, dict) else external
        return {"status": "success", "source": "external_umkm_api", "data": data}

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"status": "error", "message": "Timeout saat menghubungi API UMKM. Coba lagi beberapa saat."},
        )
    except Exception:
        logger.exception("Error fetching UMKM tenants")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"status": "error", "message": "Gagal mengambil data dari API eksternal kelompok UMKM."},
        )


async def get_discounts(is_aktif_bool: bool | None, tenant_id: str) -> dict:
    if settings.UMKM_USE_MOCK:
        data = list(_MOCK_DISCOUNTS)
        if tenant_id:
            data = [d for d in data if d["tenant_id"] == tenant_id]
        if is_aktif_bool is True:
            data = [d for d in data if d["is_aktif"]]
        elif is_aktif_bool is False:
            data = [d for d in data if not d["is_aktif"]]
        return {"status": "success", "data": data}

    api_base = _get_umkm_base()
    if not api_base:
        return {"status": "success", "data": []}

    params: dict = {}
    if tenant_id:
        params["tenant_id"] = tenant_id
    if is_aktif_bool is not None:
        params["is_aktif"] = is_aktif_bool

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{api_base.rstrip('/')}/api/public/diskon",
                params=params,
                headers={"Accept": "application/json"},
            )
        resp.raise_for_status()
        external = resp.json()
        data = external.get("data", []) if isinstance(external, dict) else external
        return {"status": "success", "data": data}

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"status": "error", "message": "Timeout saat menghubungi API UMKM."},
        )
    except Exception:
        logger.exception("Error fetching UMKM discounts")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"status": "error", "message": "Gagal mengambil data diskon dari API eksternal kelompok UMKM."},
        )


async def get_registrations(reg_status: str) -> dict:
    api_base = _get_umkm_base()
    if not api_base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "message": "UMKM_API_BASE_URL belum dikonfigurasi. Hubungkan ke UMKM Backend terlebih dahulu.",
            },
        )

    params: dict = {}
    if reg_status:
        params["status"] = reg_status

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{api_base}/api/admin/registrations",
                params=params,
                headers=_admin_headers(),
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"status": "error", "message": "Timeout saat menghubungi UMKM Backend."},
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.content else {"status": "error", "message": "Error dari UMKM Backend."},
        )
    except Exception:
        logger.exception("Error fetching UMKM registrations")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"status": "error", "message": "Gagal mengambil data pendaftaran dari UMKM Backend."},
        )


async def patch_registration(umkm_id: str, new_status: str) -> dict:
    api_base = _get_umkm_base()
    if not api_base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "message": "UMKM_API_BASE_URL belum dikonfigurasi."},
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.patch(
                f"{api_base}/api/admin/registrations/{umkm_id}",
                json={"status": new_status},
                headers=_admin_headers(),
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"status": "error", "message": "Timeout saat menghubungi UMKM Backend."},
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.content else {"status": "error", "message": "Error dari UMKM Backend."},
        )
    except Exception:
        logger.exception("Error patching UMKM registration %s", umkm_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"status": "error", "message": "Gagal memperbarui status pendaftaran di UMKM Backend."},
        )
