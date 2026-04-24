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
    pip install --no-cache-dir --index-url https://pypi.org/simple --timeout 180 --retries 5 -r requirements.txt

RUN pip install playwright --break-system-packages
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

# Celery/Django runtime hardening: run as non-root uid/gid 1000.
RUN groupadd -r celery && useradd -r -g celery -u 1000 celery
RUN mkdir -p /app/logs /app/media /app/static && chown -R celery:celery /app
RUN chown -R celery:celery /app
USER celery

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM development AS production

USER root
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

USER appuser

CMD ["gunicorn", "Plateforme.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
