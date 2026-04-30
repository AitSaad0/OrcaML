# -------- STAGE 1: Builder --------
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 👉 copier fichiers séparés
COPY requirements-base.txt .
COPY requirements-auth.txt .
COPY requirements-worker.txt .
COPY requirements-cloud.txt .
COPY requirements-ml.txt .
COPY requirements-dev.txt .

RUN pip install --no-cache-dir --default-timeout=1000 --prefix=/install -r requirements-base.txt

RUN pip install --no-cache-dir --default-timeout=1000 --prefix=/install -r requirements-auth.txt

RUN pip install --no-cache-dir --default-timeout=1000 --prefix=/install -r requirements-worker.txt

RUN pip install --no-cache-dir --default-timeout=1000 --prefix=/install -r requirements-cloud.txt

RUN pip install --no-cache-dir --default-timeout=1000 --prefix=/install -r requirements-ml.txt

RUN pip install --no-cache-dir --default-timeout=1000 --prefix=/install -r requirements-dev.txt

# -------- STAGE 2: Final --------
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]