FROM python:3.11-slim AS development

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --timeout 180 --retries 10 --upgrade pip && \
    pip install --no-cache-dir --timeout 300 --retries 5 --index-url https://download.pytorch.org/whl/cpu torch torchvision && \
    pip install --no-cache-dir --index-url https://pypi.org/simple --timeout 180 --retries 5 -r requirements.txt && \
    pip install --no-cache-dir --index-url https://pypi.org/simple --timeout 120 --retries 5 prometheus-client

COPY . .

# Ensure the HuggingFace / sentence-transformers cache directory exists
ENV HF_HOME=/app/.cache \
    TRANSFORMERS_CACHE=/app/.cache/transformers \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
RUN mkdir -p /app/.cache/transformers /app/.cache/sentence_transformers \
    && chmod -R 777 /app/.cache

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

FROM development AS production

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app/.cache

USER appuser

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "2"]
