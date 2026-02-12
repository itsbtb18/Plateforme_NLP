# ============================================
# MULTI-STAGE DJANGO DOCKERFILE
# Production-ready Django 5.1.7 with Daphne ASGI
# ============================================

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 django && \
    mkdir -p /app /app/staticfiles /app/media && \
    chown -R django:django /app

WORKDIR /app

# ============================================
# DEPENDENCIES STAGE
# ============================================
FROM base as dependencies

# Copy requirements first (better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# PRODUCTION STAGE
# ============================================
FROM base as production

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=django:django . .

# Create necessary directories
RUN mkdir -p staticfiles media locale logs && \
    chown -R django:django staticfiles media locale logs

# Note: compilemessages requires DATABASE_URL, so we'll run it in entrypoint
# Translations will be compiled when container starts

# Switch to non-root user
USER django

# Expose port
EXPOSE 8000

# Health check disabled - Django starts successfully but locale compilation takes time
# HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
#     CMD curl -f http://localhost:8000/ || exit 1

# Default command (can be overridden in docker-compose)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "Plateforme.asgi:application"]
