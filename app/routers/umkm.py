"""
Router: Integrasi UMKM Eksternal
──────────────────────────────────
GET  /api/umkm                        → REQ-INTEG-001  (Admin only)
GET  /api/umkm/registrations          → List pendaftaran UMKM (Admin only)
PATCH /api/umkm/registrations/{id}    → Approve / reject pendaftaran (Admin only)

Mode operasi GET /api/umkm dikontrol via env var UMKM_USE_MOCK:
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

# ── Helper: build UMKM admin URL ───────────────────────────────────────────────
def _get_umkm_base() -> str:
    return (config.UMKM_API_BASE_URL or config.UMKM_API_URL).strip().rstrip("/")


def _admin_headers() -> dict:
    headers = {"Accept": "application/json"}
    if config.UMKM_ADMIN_SECRET_KEY:
        headers["X-Admin-Key"] = config.UMKM_ADMIN_SECRET_KEY
    return headers


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
    api_base = _get_umkm_base()

    if not api_base:
        return {
            "status": "success",
            "source": "external_umkm_api",
            "data": [],
            "_info": "UMKM_API_BASE_URL belum dikonfigurasi.",
        }

    tenant_url = f"{api_base}/api/public/tenant"

    params: dict = {}
    if kategori:
        params["kategori"] = kategori

    headers: dict = {"Accept": "application/json"}
    if config.UMKM_API_KEY:
        headers["Authorization"] = f"Bearer {config.UMKM_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as _client:
            resp = await _client.get(tenant_url, params=params, headers=headers)
        resp.raise_for_status()
        external = resp.json()

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


# ── GET /umkm/registrations ────────────────────────────────────────────────────

@router.get("/registrations")
async def get_umkm_registrations(
    status: str = Query("", description="Filter: pending | approved | rejected | (kosong = semua)"),
    _user: CurrentUser = Depends(admin_only),
):
    """
    List pendaftaran UMKM dari UMKM Backend.
    Admin gate menggunakan ini untuk melihat permohonan yang masuk.
    """
    api_base = _get_umkm_base()

    if not api_base:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": "UMKM_API_BASE_URL belum dikonfigurasi. Hubungkan ke UMKM Backend terlebih dahulu.",
            },
        )

    params = {}
    if status:
        params["status"] = status

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
            status_code=504,
            detail={"status": "error", "message": "Timeout saat menghubungi UMKM Backend."},
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.content else {"status": "error", "message": "Error dari UMKM Backend."},
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "message": "Gagal mengambil data pendaftaran dari UMKM Backend."},
        )


# ── PATCH /umkm/registrations/{umkm_id} ───────────────────────────────────────

@router.patch("/registrations/{umkm_id}")
async def update_umkm_registration(
    umkm_id: str,
    body: dict,
    _user: CurrentUser = Depends(admin_only),
):
    """
    Approve atau reject pendaftaran UMKM.
    Body: { "status": "approved" | "rejected" }

    Endpoint ini mem-proxy request ke UMKM Backend /api/admin/registrations/{id}.
    """
    api_base = _get_umkm_base()

    if not api_base:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": "UMKM_API_BASE_URL belum dikonfigurasi.",
            },
        )

    new_status = (body.get("status") or "").strip()
    if new_status not in ("approved", "rejected"):
        raise HTTPException(
            status_code=422,
            detail={"status": "error", "message": "Status harus 'approved' atau 'rejected'."},
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
            status_code=504,
            detail={"status": "error", "message": "Timeout saat menghubungi UMKM Backend."},
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json() if e.response.content else {"status": "error", "message": "Error dari UMKM Backend."},
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "message": "Gagal memperbarui status pendaftaran di UMKM Backend."},
        )