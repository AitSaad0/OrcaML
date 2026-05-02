# ── Base image ────────────────────────────────────────────────────────────────
# Using slim to keep the image small — no jupyter, no extras
FROM python:3.11-slim

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy requirements first so Docker caches this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy serving code ─────────────────────────────────────────────────────────
COPY serve.py .

# ── Environment variables (overridden at docker run time) ─────────────────────
ENV MODEL_PATH=/app/model.pkl
ENV MODEL_ID=unknown
ENV ALGORITHM=unknown

# ── Expose port ───────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Health check ──────────────────────────────────────────────────────────────
# Docker will mark the container unhealthy if /health stops responding
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Start server ──────────────────────────────────────────────────────────────
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]