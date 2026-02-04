# Phoenix Guardian - Main Application Container
# Multi-stage build for minimal image size and security
# Version: 1.0.0

# ==============================================================================
# Stage 1: Builder - Install dependencies
# ==============================================================================
FROM python:3.11-slim AS builder

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies (needed for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies to user directory
RUN pip install --user --no-cache-dir -r requirements.txt

# Install gunicorn and gevent for production server
RUN pip install --user --no-cache-dir \
    gunicorn==21.2.0 \
    gevent==24.2.1 \
    psycogreen==1.0.2

# ==============================================================================
# Stage 2: Runtime - Minimal production image
# ==============================================================================
FROM python:3.11-slim

LABEL maintainer="Phoenix Guardian Team <security@phoenix-guardian.io>" \
      version="1.0.0" \
      description="Phoenix Guardian AI Security System - Main Application" \
      org.opencontainers.image.source="https://github.com/phoenix-guardian/phoenix-guardian"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    # Application configuration
    APP_HOME=/app \
    APP_USER=phoenix \
    APP_UID=1000 \
    APP_GID=1000 \
    # Runtime configuration
    WORKERS=8 \
    WORKER_CLASS=gevent \
    WORKER_CONNECTIONS=1000 \
    TIMEOUT=60 \
    BIND_ADDRESS=0.0.0.0:8000 \
    # Python path
    PATH="/home/phoenix/.local/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR $APP_HOME

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid $APP_GID $APP_USER \
    && useradd --uid $APP_UID --gid $APP_GID --shell /bin/bash --create-home $APP_USER

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/phoenix/.local

# Copy application code
COPY --chown=$APP_USER:$APP_USER phoenix_guardian/ ./phoenix_guardian/
COPY --chown=$APP_USER:$APP_USER docs/ ./docs/

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data /app/tmp \
    && chown -R $APP_USER:$APP_USER /app

# Switch to non-root user
USER $APP_USER

# Expose application port
EXPOSE 8000

# Health check - verify app is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Gunicorn configuration for production
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "8", \
     "--worker-class", "gevent", \
     "--worker-connections", "1000", \
     "--timeout", "60", \
     "--keep-alive", "5", \
     "--max-requests", "10000", \
     "--max-requests-jitter", "1000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--capture-output", \
     "--enable-stdio-inheritance", \
     "--log-level", "info", \
     "phoenix_guardian.app:create_app()"]
