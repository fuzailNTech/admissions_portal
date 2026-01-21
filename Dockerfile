# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /code

# Copy installed packages
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY . .
# ---------------------------------------------------------
# ⚠️ TEMPORARY ONLY – REMOVE LATER
# ---------------------------------------------------------
# This runs database migrations at CONTAINER STARTUP.
# This is NOT recommended for production long-term because:
# - It runs on every restart
# - It can cause race conditions with multiple instances
#
# Proper solution:
# 👉 Move this to Render's "Pre-Deploy Command":
#    python -m alembic upgrade head
#
# REMOVE THIS LINE once Pre-Deploy Command is configured.

CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 9000"]
