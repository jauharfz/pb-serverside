# ── Build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

# [FIX] HuggingFace Spaces Docker wajib listen di port 7860.
# EXPOSE tidak support shell default ${VAR:-default}, harus eksplisit.
EXPOSE 7860

# HuggingFace otomatis inject PORT=7860 — tidak perlu set manual di Secrets.
# WORKERS default 1 untuk free tier HuggingFace CPU Basic.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]