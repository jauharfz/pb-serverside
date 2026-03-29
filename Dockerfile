# ── Build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install dependencies terlebih dahulu (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages dan semua executables dari builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source code
COPY . .

EXPOSE ${PORT:-8000}

# PORT      — port listen (default 8000, Railway/Render/Fly set otomatis)
# WORKERS   — jumlah Uvicorn worker (default 1 untuk free tier, naikkan di paid)
# APP_DEBUG — "true" untuk verbose logging (jangan di production)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1}"]
