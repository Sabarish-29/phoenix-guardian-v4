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

EXPOSE 8000

# Use gunicorn with uvicorn workers for production
CMD ["gunicorn", "phoenix_guardian.api.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
