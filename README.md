# Sistem NFC Peken Banyumasan — FastAPI Backend

## Struktur Proyek

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py          # Pydantic Settings (env vars)
│   │   ├── logging.py         # Setup logging terpusat
│   │   └── dependencies.py    # Auth deps: require_auth, admin_only
│   ├── db/
│   │   └── client.py          # Supabase client singleton
│   ├── schemas/               # Pydantic request models
│   │   ├── auth.py
│   │   ├── events.py
│   │   ├── members.py
│   │   ├── nfc.py
│   │   └── visitors.py
│   ├── services/              # Business logic
│   │   ├── auth_service.py
│   │   ├── dashboard_service.py
│   │   ├── event_service.py
│   │   ├── member_service.py
│   │   ├── nfc_service.py
│   │   ├── report_service.py
│   │   ├── umkm_service.py    # UMKM proxy + mock data
│   │   └── visitor_service.py
│   ├── routers/               # HTTP handlers (thin layer)
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── discounts.py
│   │   ├── events.py
│   │   ├── members.py
│   │   ├── nfc.py
│   │   ├── reports.py
│   │   ├── umkm.py
│   │   └── visitors.py
│   └── main.py                # App factory + lifespan
├── main.py                    # Entrypoint (uvicorn)
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Setup

```bash
cp .env.example .env
# Edit .env dengan nilai Supabase dan konfigurasi lainnya

pip install -r requirements.txt
python main.py
```

## API Docs

- Swagger UI : http://localhost:8000/docs
- ReDoc      : http://localhost:8000/redoc
