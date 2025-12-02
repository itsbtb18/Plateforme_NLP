# 🚀 NLP Platform - Complete Docker Deployment Guide

> **Production-Ready Docker Architecture for Django + FastAPI NLP Platform**  
> Local PostgreSQL | Redis | Elasticsearch | Nginx Reverse Proxy

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start (Development)](#quick-start-development)
4. [Production Deployment](#production-deployment)
5. [Offline CentOS Deployment](#offline-centos-deployment)
6. [Maintenance & Updates](#maintenance--updates)
7. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

### Services Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Nginx (Port 80)                      │
│            Reverse Proxy & Static File Server               │
└───────────┬─────────────────────────────────┬───────────────┘
            │                                 │
            ▼                                 ▼
    ┌───────────────┐                 ┌──────────────┐
    │    Django     │                 │   FastAPI    │
    │  (Daphne)     │                 │  (Uvicorn)   │
    │   Port 8000   │                 │  Port 8000   │
    │  WebSockets   │                 │  Chatbot API │
    └───────┬───────┘                 └──────┬───────┘
            │                                │
            │         ┌──────────────────────┘
            │         │
            ▼         ▼
    ┌──────────────────────┐
    │  PostgreSQL + pgvector│
    │      Port 5432        │
    └──────────────────────┘
            │
    ┌───────┴────────┐
    ▼                ▼
┌─────────┐    ┌──────────────┐
│  Redis  │    │Elasticsearch │
│  6379   │    │     9200     │
└─────────┘    └──────────────┘
```

### Key Features

✅ **Local PostgreSQL** - No external dependencies (removed Neon DB)  
✅ **pgvector Extension** - Vector similarity search for embeddings  
✅ **Multi-stage Builds** - Optimized Docker images  
✅ **Health Checks** - Automatic service monitoring  
✅ **Persistent Data** - Docker volumes for databases  
✅ **Production-Ready** - Non-root users, security headers  
✅ **Offline Deployment** - USB-based updates for air-gapped systems  

---

## 📦 Prerequisites

### Development Machine

- **Docker Desktop** 24.0+ (Windows/Mac) or **Docker Engine** 24.0+ (Linux)
- **Docker Compose** v2.20+
- **Git** 2.40+
- **Python** 3.11+ (for local development)

### Production Server (CentOS)

- **CentOS** 7+ or **RHEL** 7+
- **Docker** 24.0+
- **Docker Compose** v2.20+
- Minimum **8GB RAM** (16GB recommended)
- **50GB** free disk space

### Required Credentials

1. **Groq API Key** - Get from [https://console.groq.com](https://console.groq.com)
2. (Optional) **Google OAuth** credentials for social authentication

---

## 🚀 Quick Start (Development)

### Step 1: Clone Repository

```bash
cd d:\PFE
git clone <your-repo-url> Plateforme_NLP
cd Plateforme_NLP
```

### Step 2: Create Environment File

```bash
# Copy example file
cp .env.example .env

# Edit with your credentials
notepad .env
```

**Required Changes in `.env`:**

```bash
# Change these values:
GROQ_API_KEY=gsk_your_actual_groq_api_key_here

# Optional: Change default passwords
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
```

### Step 3: Build Images

```bash
docker-compose build
```

**Expected Output:**
```
[+] Building 120.5s (45/45) FINISHED
 => [django internal] load build definition from Dockerfile
 => [fastapi internal] load build definition from Dockerfile
 ...
 => => naming to docker.io/library/plateforme_nlp-django
 => => naming to docker.io/library/plateforme_nlp-fastapi
```

### Step 4: Start Services

```bash
docker-compose up -d
```

**Services Starting:**
```
✅ PostgreSQL (db)          - Port 5432
✅ Redis (redis)             - Port 6379
✅ Elasticsearch             - Port 9200
✅ Django (django)           - Port 8000
✅ FastAPI (fastapi)         - Port 8001
✅ Nginx (nginx)             - Port 80
```

### Step 5: Initialize Database

```bash
# Run Django migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser

# Initialize FastAPI database and pgvector
docker-compose exec fastapi python init_db.py
```

### Step 6: Ingest Data (FastAPI Chatbot)

```bash
# Ingest platform documentation
docker-compose exec fastapi python app/ingestion/ingest_platform_docs.py

# Ingest NLP knowledge base
docker-compose exec fastapi python app/ingestion/ingest_nlp_knowledge.py

# Ingest research resources
docker-compose exec fastapi python app/ingestion/ingest_resources.py
```

### Step 7: Access Application

- **Main Platform**: http://localhost
- **Django Admin**: http://localhost/admin
- **FastAPI Docs**: http://localhost/api/docs
- **FastAPI Health**: http://localhost/api/health

---

## 🏭 Production Deployment

### Step 1: Prepare Production Environment

```bash
# Copy production env template
cp .env.production .env

# Edit with production credentials
nano .env
```

**Critical Production Changes:**

```bash
# MUST CHANGE THESE:
DJANGO_SECRET_KEY=<generate-with-python-secrets-token-urlsafe-50>
POSTGRES_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Update with production credentials:
GROQ_API_KEY=<production-key>

# Media storage (ensure volume is properly mounted)
MEDIA_ROOT=/app/media
```

**Generate Django Secret Key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 2: Update Django Settings for Production

Verify `Plateforme/Plateforme/settings.py`:

```python
# Remove any hardcoded Neon DB references
DATABASE_URL = config('DATABASE_URL', default='', cast=str)
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in .env file")

DATABASES = {
    'default': dj_database_url.parse(str(DATABASE_URL), conn_max_age=600)
}
```

### Step 3: Update Channel Layers for Redis

In `Plateforme/Plateforme/settings.py`:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config('REDIS_URL', default='redis://localhost:6379/0')],
        },
    },
}
```

Install `channels-redis` in `Plateforme/requirements.txt`:
```
channels-redis>=4.1.0
```

### Step 4: Build Production Images

```bash
docker-compose build --no-cache
```

### Step 5: Deploy with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f
```

### Step 6: SSL/TLS Configuration (Recommended)

For HTTPS, add SSL certificates to Nginx:

**Update `nginx/conf.d/default.conf`:**
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # ... rest of configuration
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

**Mount SSL certificates in `docker-compose.yml`:**
```yaml
nginx:
  volumes:
    - ./nginx/ssl:/etc/nginx/ssl:ro
    # ... other volumes
```

---

## 💾 Offline CentOS Deployment

> **Use Case**: Production CentOS server with **no internet access**  
> **Update Cycle**: Every 3 months via USB drive

### Preparation on Development Machine

#### 1. Save All Docker Images

```bash
# Build images
docker-compose build --no-cache

# Save images to tar files
docker save -o nlp_images.tar \
  plateforme_nlp-django:latest \
  plateforme_nlp-fastapi:latest \
  ankane/pgvector:latest \
  redis:7-alpine \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0 \
  nginx:1.25-alpine

# Compress for smaller size
gzip nlp_images.tar
# Result: nlp_images.tar.gz (~2-3 GB)
```

#### 2. Prepare Deployment Package

Create USB deployment structure:

```
USB_DRIVE/
├── nlp_images.tar.gz           # Docker images
├── docker-compose.yml           # Orchestration
├── .env.production             # Environment config
├── nginx/                      # Nginx configs
│   ├── nginx.conf
│   └── conf.d/
│       └── default.conf
├── init-db.sql                 # Database init
├── Plateforme/                 # Django source
│   ├── Dockerfile
│   ├── requirements.txt
│   └── ... (all Django files)
├── fastapi_chatbot/            # FastAPI source
│   ├── Dockerfile
│   ├── requirements.txt
│   └── ... (all FastAPI files)
└── DEPLOYMENT_GUIDE.md         # This file
```

#### 3. Copy to USB Drive

```bash
# Create deployment package
mkdir -p /mnt/usb/nlp_deployment
cp -r . /mnt/usb/nlp_deployment/
cp nlp_images.tar.gz /mnt/usb/nlp_deployment/
```

### Installation on CentOS Server

#### 1. Install Docker (If Not Installed)

```bash
# Install Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
sudo systemctl start docker
sudo systemctl enable docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. Load Docker Images from USB

```bash
# Mount USB drive
sudo mount /dev/sdb1 /mnt/usb

# Navigate to deployment folder
cd /mnt/usb/nlp_deployment

# Load images
gunzip -c nlp_images.tar.gz | docker load

# Verify images loaded
docker images
```

**Expected Output:**
```
REPOSITORY                                            TAG       IMAGE ID       SIZE
plateforme_nlp-django                                 latest    abc123...     1.2GB
plateforme_nlp-fastapi                                latest    def456...     1.5GB
ankane/pgvector                                       latest    ghi789...     380MB
redis                                                 7-alpine  jkl012...     30MB
docker.elastic.co/elasticsearch/elasticsearch         8.11.0    mno345...     1.3GB
nginx                                                 1.25-alpine pqr678...  40MB
```

#### 3. Copy Files to Server

```bash
# Create project directory
sudo mkdir -p /opt/nlp_platform
cd /opt/nlp_platform

# Copy files from USB
sudo cp -r /mnt/usb/nlp_deployment/* .

# Set permissions
sudo chown -R $USER:$USER /opt/nlp_platform
```

#### 4. Configure Environment

```bash
# Copy production environment
cp .env.production .env

# Edit with production credentials
nano .env
```

#### 5. Deploy Application

```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

#### 6. Initialize Application

```bash
# Run Django migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser

# Collect static files
docker-compose exec django python manage.py collectstatic --noinput

# Initialize FastAPI database
docker-compose exec fastapi python init_db.py

# Ingest data
docker-compose exec fastapi python app/ingestion/ingest_platform_docs.py
docker-compose exec fastapi python app/ingestion/ingest_nlp_knowledge.py
```

#### 7. Configure Firewall

```bash
# Allow HTTP
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https

# Or allow specific port
sudo firewall-cmd --permanent --add-port=80/tcp

# Reload firewall
sudo firewall-cmd --reload
```

#### 8. Set Up Systemd Service (Auto-start on Boot)

Create `/etc/systemd/system/nlp-platform.service`:

```ini
[Unit]
Description=NLP Platform Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/nlp_platform
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable nlp-platform.service
sudo systemctl start nlp-platform.service
```

---

## 🔄 Maintenance & Updates

### Quarterly Update Process (Every 3 Months)

#### On Development Machine

```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild images
docker-compose build --no-cache

# 3. Save updated images
docker save -o nlp_images_v2.tar \
  plateforme_nlp-django:latest \
  plateforme_nlp-fastapi:latest

# 4. Compress
gzip nlp_images_v2.tar

# 5. Copy to USB with updated source code
```

#### On Production Server

```bash
# 1. Backup current data
docker-compose exec db pg_dump -U nlp_admin nlp_platform > backup_$(date +%Y%m%d).sql

# 2. Stop services
docker-compose down

# 3. Load new images
gunzip -c /mnt/usb/nlp_images_v2.tar.gz | docker load

# 4. Update source code
cp -r /mnt/usb/nlp_deployment/* .

# 5. Start services
docker-compose up -d

# 6. Run migrations
docker-compose exec django python manage.py migrate
```

### Database Backup & Restore

#### Backup

```bash
# Full database backup
docker-compose exec db pg_dump -U nlp_admin nlp_platform | gzip > backup_$(date +%Y%m%d).sql.gz

# Backup with Docker volume
docker run --rm -v plateforme_nlp_postgres_data:/data -v $(pwd):/backup \
  busybox tar czf /backup/postgres_backup_$(date +%Y%m%d).tar.gz /data
```

#### Restore

```bash
# Restore from SQL dump
gunzip -c backup_20240101.sql.gz | docker-compose exec -T db psql -U nlp_admin nlp_platform

# Restore from volume backup
docker run --rm -v plateforme_nlp_postgres_data:/data -v $(pwd):/backup \
  busybox tar xzf /backup/postgres_backup_20240101.tar.gz -C /
```

### Log Management

```bash
# View logs
docker-compose logs -f --tail=100 django
docker-compose logs -f --tail=100 fastapi

# Clear logs
truncate -s 0 $(docker inspect --format='{{.LogPath}}' nlp_django)
truncate -s 0 $(docker inspect --format='{{.LogPath}}' nlp_fastapi)
```

### Resource Monitoring

```bash
# Check container stats
docker stats

# Check disk usage
docker system df

# Clean up unused resources
docker system prune -a --volumes
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Database Connection Failed

**Symptom:**
```
django.db.utils.OperationalError: could not connect to server
```

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Verify DATABASE_URL in .env
cat .env | grep DATABASE_URL

# Restart database
docker-compose restart db
```

#### 2. Port Already in Use

**Symptom:**
```
ERROR: for nginx  Cannot start service nginx: driver failed programming external connectivity
```

**Solution:**
```bash
# Find process using port
netstat -ano | findstr :80  # Windows
lsof -i :80                  # Linux/Mac

# Change port in docker-compose.yml
ports:
  - "8080:80"  # Use different port
```

#### 3. Nginx 502 Bad Gateway

**Symptom:** Browser shows "502 Bad Gateway"

**Solution:**
```bash
# Check backend services
docker-compose ps django fastapi

# Check nginx logs
docker-compose logs nginx

# Verify upstream configuration
docker-compose exec nginx cat /etc/nginx/conf.d/default.conf

# Restart services
docker-compose restart django fastapi nginx
```

#### 4. Out of Memory

**Symptom:**
```
Elasticsearch: java.lang.OutOfMemoryError
```

**Solution:**
```bash
# Reduce Elasticsearch heap in docker-compose.yml
environment:
  - "ES_JAVA_OPTS=-Xms256m -Xmx256m"

# Or increase Docker resources in Docker Desktop settings
```

#### 5. pgvector Extension Not Found

**Symptom:**
```
django.db.utils.ProgrammingError: type "vector" does not exist
```

**Solution:**
```bash
# Recreate database with pgvector
docker-compose exec db psql -U nlp_admin -d nlp_platform -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Or restart with fresh volume
docker-compose down -v
docker-compose up -d
```

### Health Check Commands

```bash
# Check all services
docker-compose ps

# Test Django
curl http://localhost/
curl http://localhost/admin/

# Test FastAPI
curl http://localhost/api/health
curl http://localhost/api/docs

# Test Database
docker-compose exec db psql -U nlp_admin -d nlp_platform -c "SELECT version();"

# Test Redis
docker-compose exec redis redis-cli -a redis123 ping

# Test Elasticsearch
curl http://localhost:9200/_cluster/health
```

---

## 📊 Performance Optimization

### Production Tuning

#### PostgreSQL (docker-compose.yml)

```yaml
db:
  command:
    - "postgres"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "effective_cache_size=1GB"
    - "-c"
    - "work_mem=16MB"
```

#### Django (Dockerfile - Gunicorn Alternative)

For high-traffic scenarios, replace Daphne with Gunicorn + Uvicorn workers:

```dockerfile
CMD ["gunicorn", "Plateforme.asgi:application", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
```

Update `requirements.txt`:
```
gunicorn>=21.2.0
uvicorn[standard]>=0.25.0
```

#### Nginx Caching

Add to `nginx/conf.d/default.conf`:

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;

location / {
    proxy_cache my_cache;
    proxy_cache_valid 200 10m;
    proxy_cache_use_stale error timeout updating;
    # ... rest of config
}
```

---

## 🛡️ Security Checklist

- [ ] Changed all default passwords in `.env`
- [ ] Generated strong Django `SECRET_KEY`
- [ ] Set `DEBUG=False` in production
- [ ] Configured `ALLOWED_HOSTS` with actual domain
- [ ] Enabled SSL/TLS certificates for HTTPS
- [ ] Configured firewall rules (only allow 80/443)
- [ ] Set up regular database backups
- [ ] Enabled Docker security scanning: `docker scan <image>`
- [ ] Limited container resources (CPU/memory)
- [ ] Disabled root SSH login on server
- [ ] Set up log monitoring and alerts

---

## 📞 Support & Contacts

- **Project Documentation**: `./README.md`
- **FastAPI Docs**: `./fastapi_chatbot/README.md`
- **Django Chatbot**: `./Plateforme/chatbot/README.md`

---

## ✅ Deployment Checklist

### Pre-Deployment
- [ ] Docker & Docker Compose installed
- [ ] All environment variables configured in `.env`
- [ ] Groq API key obtained and set
- [ ] Firewall rules configured
- [ ] Media volume properly mounted

### Initial Deployment
- [ ] Images built successfully
- [ ] All services started and healthy
- [ ] Database migrations completed
- [ ] Superuser created
- [ ] Static files collected
- [ ] FastAPI database initialized
- [ ] Data ingestion completed

### Post-Deployment
- [ ] Application accessible via browser
- [ ] Admin panel working
- [ ] Chatbot responding correctly
- [ ] WebSockets functional
- [ ] Search working (Elasticsearch)
- [ ] File uploads working (local storage)
- [ ] SSL/TLS configured (production)
- [ ] Backup system in place
- [ ] Monitoring configured

---

**Last Updated**: 2024  
**Version**: 1.0.0  
**Tested on**: Docker 24.0.7, Docker Compose v2.23.0, CentOS 7.9
