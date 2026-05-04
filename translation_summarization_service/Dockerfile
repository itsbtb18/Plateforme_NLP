FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

<<<<<<< HEAD
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
=======
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
