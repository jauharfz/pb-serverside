"""
Blueprint: Integrasi UMKM Eksternal
────────────────────────────────────
GET /api/umkm → REQ-INTEG-001  (Admin only)

Flask API bertindak sebagai proxy ke API eksternal kelompok UMKM.
URL dan API key dikonfigurasi via environment variable:
  UMKM_API_URL  → endpoint API eksternal
  UMKM_API_KEY  → bearer token API eksternal (jika ada)
"""

import os

import requests as http
from flask import Blueprint, jsonify, request

from app.middleware.auth import admin_only

umkm_bp = Blueprint("umkm", __name__)

_TIMEOUT = 10  # detik


@umkm_bp.route("/umkm", methods=["GET"])
@admin_only
def get_umkm():
    api_url = os.environ.get("UMKM_API_URL", "").strip()
    api_key = os.environ.get("UMKM_API_KEY", "").strip()

    if not api_url:
        return jsonify({
            "status": "error",
            "message": "Gagal mengambil data dari API eksternal kelompok UMKM",
        }), 502

    # ── Forward query params yang relevan ─────────────────────────────────
    params: dict = {}
    if request.args.get("kategori"):
        params["kategori"] = request.args["kategori"]
    if request.args.get("is_aktif"):
        params["is_aktif"] = request.args["is_aktif"]

    headers: dict = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = http.get(api_url, params=params, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        external = resp.json()

        # Normalisasi: API eksternal bisa mengembalikan list atau {"data": [...]}
        data = external if isinstance(external, list) else external.get("data", [])

        return jsonify({
            "status": "success",
            "source": "external_umkm_api",
            "data": data,
        }), 200

    except http.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "Gagal mengambil data dari API eksternal kelompok UMKM",
        }), 502
    except http.exceptions.HTTPError:
        return jsonify({
            "status": "error",
            "message": "Gagal mengambil data dari API eksternal kelompok UMKM",
        }), 502
    except Exception:
        return jsonify({
            "status": "error",
            "message": "Gagal mengambil data dari API eksternal kelompok UMKM",
        }), 502
