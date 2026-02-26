# ============================================
# MULTI-STAGE FASTAPI DOCKERFILE
# Production-ready FastAPI with Uvicorn
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
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 fastapi && \
    mkdir -p /app /app/.cache && \
    chown -R fastapi:fastapi /app

WORKDIR /app

# ============================================
# DEPENDENCIES STAGE
# ============================================
FROM base as dependencies

# Copy requirements first (better layer caching)
COPY requirements.txt .

# Install PyTorch CPU-only version first (smaller, faster download)
# Using extended timeout and retries for large package
RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
RUN pip install --no-cache-dir --timeout 120 --retries 3 -r requirements.txt

# Download sentence-transformers model during build
# This speeds up container startup significantly
RUN python -c "from sentence_transformers import SentenceTransformer; \
    model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2'); \
    print('Model downloaded successfully')"

# ============================================
# PRODUCTION STAGE
# ============================================
FROM base as production

# Copy installed packages from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin
# Copy pre-downloaded model cache
COPY --from=dependencies /root/.cache /home/fastapi/.cache

# Copy application code
COPY --chown=fastapi:fastapi . .

# Create necessary directories
RUN mkdir -p logs && \
    chown -R fastapi:fastapi logs

# Fix cache permissions (create directory if it doesn't exist)
RUN mkdir -p /home/fastapi/.cache && \
    chown -R fastapi:fastapi /home/fastapi/.cache

# Switch to non-root user
USER fastapi

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "120"]
