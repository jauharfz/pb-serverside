# Flask API — Sistem Pemindai NFC Peken Banyumasan

Backend RESTful API untuk Sistem Pemindai NFC Masuk-Keluar Event Peken Banyumasan.
Dibangun dengan **Flask (Python)** dan terintegrasi dengan **Supabase (PostgreSQL)**.

---

## Struktur Project

```
peken-api/
├── app/
│   ├── __init__.py              # create_app factory
│   ├── config.py                # Konfigurasi dari .env
│   ├── extensions.py            # Supabase client (service-role)
│   ├── middleware/
│   │   └── auth.py              # JWT verify + role decorator
│   └── blueprints/
│       ├── auth/routes.py       # POST /api/auth/login
│       ├── nfc/routes.py        # POST /api/tap
│       ├── members/routes.py    # GET/POST /api/members, PUT /api/members/<id>
│       ├── visitors/routes.py   # GET /api/visitors, POST /api/visitors/manual
│       ├── dashboard/routes.py  # GET /api/dashboard/stats
│       ├── reports/routes.py    # GET /api/reports, GET /api/reports/export
│       ├── discounts/routes.py  # GET /api/discounts
│       └── umkm/routes.py       # GET /api/umkm
├── run.py
├── requirements.txt
├── .env.example
├── Dockerfile
└── .dockerignore
```

---

## Prasyarat

- Python 3.12+
- Supabase project yang sudah di-setup (jalankan `supabase_peken_banyumasan.sql` terlebih dahulu)

---

## Setup Lokal

### 1. Clone & masuk ke direktori

```bash
cd peken-api
```

### 2. Buat virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi environment

```bash
cp .env.example .env
```

Edit `.env` dan isi nilainya:

| Variable | Cara mendapatkan |
|---|---|
| `SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Settings → API → `service_role` |
| `SUPABASE_JWT_SECRET` | Supabase Dashboard → Settings → API → JWT Secret |
| `UMKM_API_URL` | URL endpoint API kelompok UMKM |
| `UMKM_API_KEY` | Bearer token API UMKM (kosongkan jika tidak ada) |

### 5. Jalankan server development

```bash
python run.py
```

API berjalan di `http://localhost:5000`.

---

## Endpoint

| Method | Path | Auth | Deskripsi |
|---|---|---|---|
| POST | `/api/auth/login` | ✗ | Login admin/petugas |
| POST | `/api/tap` | ✗ | Tap NFC masuk/keluar (dari NFC Reader) |
| GET | `/api/members` | Admin | Daftar member |
| POST | `/api/members` | Admin | Daftarkan member baru |
| PUT | `/api/members/<id>` | Admin | Update data member |
| GET | `/api/visitors` | Admin | Data kunjungan |
| POST | `/api/visitors/manual` | Admin+Petugas | Input manual pengunjung biasa |
| GET | `/api/dashboard/stats` | Admin | Statistik real-time |
| GET | `/api/reports` | Admin | Laporan harian |
| GET | `/api/reports/export` | Admin | Ekspor PDF/Excel |
| GET | `/api/discounts` | Admin+Petugas | Daftar diskon UMKM |
| GET | `/api/umkm` | Admin | Data tenant dari API eksternal |

### Auth Header

Semua endpoint bertanda **Admin** atau **Admin+Petugas** memerlukan:

```
Authorization: Bearer <token>
```

Token diperoleh dari `POST /api/auth/login`.

---

## Deploy ke Railway

1. Push project ke GitHub.
2. Buka [railway.app](https://railway.app) → New Project → Deploy from GitHub Repo.
3. Tambahkan environment variables (sesuai `.env.example`) di tab **Variables**.
4. Railway otomatis mendeteksi `Dockerfile` dan men-deploy.
5. Copy **Public Domain** yang diberikan Railway → update `VITE_API_BASE_URL` di project React.

## Deploy ke Render

1. Buka [render.com](https://render.com) → New → Web Service → Connect GitHub Repo.
2. Pilih **Docker** sebagai environment.
3. Tambahkan environment variables di tab **Environment**.
4. Render otomatis inject `PORT` — tidak perlu diubah.

---

## Catatan Penting

- **`POST /api/tap`** tidak memerlukan JWT. Endpoint ini hanya dipanggil oleh NFC Reader hardware melalui HTTPS.
- **Service Role Key** digunakan di server-side dan mem-bypass Supabase RLS. Jangan pernah expose key ini ke frontend.
- Akun pengguna (Admin/Petugas) dibuat melalui **Supabase Dashboard → Authentication → Users**. Sertakan `nama` dan `role` di kolom **User Metadata** saat membuat user:
  ```json
  { "nama": "Ahmad Al-Farizi", "role": "admin" }
  ```
  Trigger `trg_auto_create_admin` akan otomatis membuat baris di tabel `admin`.
