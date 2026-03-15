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

# Copy installed packages dari builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy source code
COPY . .

# Port default (Railway/Render akan inject PORT via env)
EXPOSE 5000

# Gunicorn: 2 worker, timeout 60 detik
# Railway/Render inject PORT → gunicorn bind ke 0.0.0.0:$PORT
CMD ["sh", "-c", "gunicorn run:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 60 --access-logfile -"]
