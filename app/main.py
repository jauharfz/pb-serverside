"""
Sistem Pemindai NFC Peken Banyumasan — FastAPI
───────────────────────────────────────────────
Konversi dari Flask (blueprints) → FastAPI (routers).

URL prefix /api dipertahankan agar kompatibel dengan frontend
yang sudah ada tanpa perlu perubahan konfigurasi.
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.routers import auth, dashboard, discounts, events, members, nfc, reports, umkm, visitors, profile

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sistem NFC Peken Banyumasan",
    version="1.0.0",
    description="API Backend Sistem Pemindai NFC — Peken Banyumasan",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/auth")
app.include_router(nfc.router,       prefix="/api")
app.include_router(members.router,   prefix="/api")
app.include_router(visitors.router,  prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(reports.router,   prefix="/api")
app.include_router(discounts.router, prefix="/api")
app.include_router(umkm.router,      prefix="/api")
app.include_router(events.router,    prefix="/api")
app.include_router(profile.router, prefix="/api")
