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

EXPOSE ${PORT:-7860}
# PORT      — port listen (default 7860, Railway/Render/Fly set otomatis)
# WORKERS   — jumlah Gunicorn worker (default 1 untuk free tier, naikkan di paid)
# FLASK_DEBUG — "true" untuk verbose logging (jangan di production)
CMD ["sh", "-c", "gunicorn run:app --bind 0.0.0.0:${PORT:-7860} --workers ${WORKERS:-1} --timeout 60 --access-logfile -"]