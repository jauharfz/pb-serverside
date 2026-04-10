"""
app/main.py
────────────
FastAPI application factory.
Gunakan lifespan untuk setup (logging) saat startup.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.routers import auth, dashboard, discounts, events, members, nfc, reports, umkm, visitors


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(debug=settings.APP_DEBUG)
    yield


app = FastAPI(
    title="Sistem NFC Peken Banyumasan",
    version="1.0.0",
    description="API Backend Sistem Pemindai NFC — Peken Banyumasan",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Prefix /api dipertahankan agar kompatibel dengan frontend yang sudah ada.

app.include_router(auth.router,      prefix="/api")
app.include_router(nfc.router,       prefix="/api")
app.include_router(members.router,   prefix="/api")
app.include_router(visitors.router,  prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(reports.router,   prefix="/api")
app.include_router(discounts.router, prefix="/api")
app.include_router(umkm.router,      prefix="/api")
app.include_router(events.router,    prefix="/api")
