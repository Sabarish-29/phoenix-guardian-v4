# Phoenix Guardian Backend - Render Deployment
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

WORKDIR /app

# Install system deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (production only - no torch)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY phoenix_guardian/ ./phoenix_guardian/
# Note: On Render, env vars are injected via the dashboard/render.yaml.
# .env.example is included as a fallback template only.
COPY .env.example ./.env

# Render sets PORT env var (usually 10000); fallback to 8000 for local
EXPOSE ${PORT:-8000}

# Use gunicorn with uvicorn workers for production
# - 1 worker: avoids race conditions on startup (enum creation) and fits free-tier memory
# - Shell form to expand $PORT at runtime
CMD gunicorn phoenix_guardian.api.main:app \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -
