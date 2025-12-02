# NLP Platform - Docker Deployment

Complete Docker architecture with local PostgreSQL, Redis, Elasticsearch, and Nginx.

## 📁 Project Structure

```
Plateforme_NLP/
├── docker-compose.yml          # Main orchestration
├── init-db.sql                 # PostgreSQL initialization
├── .env.example                # Development environment template
├── .env.production             # Production environment template
├── DOCKER_DEPLOYMENT.md        # Complete deployment guide
├── DOCKER_COMMANDS.md          # Quick command reference
├── nginx/                      # Nginx reverse proxy
│   ├── nginx.conf
│   └── conf.d/
│       └── default.conf
├── Plateforme/                 # Django application
│   ├── Dockerfile
│   ├── .dockerignore
│   └── ... (Django files)
└── fastapi_chatbot/            # FastAPI application
    ├── Dockerfile
    ├── .dockerignore
    └── ... (FastAPI files)
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Copy environment file
cp .env.example .env

# Edit with your credentials
notepad .env
```

**Required Changes:**
```bash
GROQ_API_KEY=your_actual_groq_api_key
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

### 2. Build & Start

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### 3. Initialize

```bash
# Django migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser

# FastAPI database
docker-compose exec fastapi python init_db.py

# Ingest data
docker-compose exec fastapi python app/ingestion/ingest_platform_docs.py
```

### 4. Access

- **Main Platform**: http://localhost
- **Admin Panel**: http://localhost/admin
- **API Docs**: http://localhost/api/docs

## 📊 Services

| Service | Port | Description |
|---------|------|-------------|
| **Nginx** | 80 | Reverse proxy & static files |
| **Django** | 8000 | Main web application (Daphne) |
| **FastAPI** | 8001 | Chatbot API (Uvicorn) |
| **PostgreSQL** | 5432 | Database with pgvector |
| **Redis** | 6379 | Django Channels backend |
| **Elasticsearch** | 9200 | Search functionality |

## 🔄 Common Commands

```bash
# View logs
docker-compose logs -f django
docker-compose logs -f fastapi

# Restart service
docker-compose restart django

# Stop all
docker-compose down

# Clean restart
docker-compose down && docker-compose up -d --build
```

## 📚 Documentation

- **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** - Complete deployment guide
  - Architecture overview
  - Development setup
  - Production deployment
  - Offline CentOS deployment
  - Troubleshooting

- **[DOCKER_COMMANDS.md](DOCKER_COMMANDS.md)** - Quick command reference
  - Build & start commands
  - Service management
  - Database operations
  - Debugging tools

## 🏭 Production Deployment

See **[DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)** for:
- Production environment setup
- SSL/TLS configuration
- Offline deployment to CentOS
- Backup & restore procedures
- Performance tuning

## 🔧 Troubleshooting

### Database Connection Issues
```bash
docker-compose logs db
docker-compose restart db
```

### Port Conflicts
```bash
# Change ports in docker-compose.yml
ports:
  - "8080:80"  # Use different port
```

### Check Service Health
```bash
curl http://localhost/
curl http://localhost/api/health
docker-compose ps
```

## 🛡️ Security

✅ Local PostgreSQL (no external dependencies)  
✅ Non-root users in containers  
✅ Health checks enabled  
✅ Security headers configured  
✅ Production secrets via environment variables  

## 💾 Backup

```bash
# Backup database
docker-compose exec db pg_dump -U nlp_admin nlp_platform > backup.sql

# Restore
cat backup.sql | docker-compose exec -T db psql -U nlp_admin nlp_platform
```

## 📞 Support

For detailed instructions, see:
- **Complete Guide**: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
- **Command Reference**: [DOCKER_COMMANDS.md](DOCKER_COMMANDS.md)
- **FastAPI Docs**: [fastapi_chatbot/README.md](fastapi_chatbot/README.md)
- **Django Chatbot**: [Plateforme/chatbot/README.md](Plateforme/chatbot/README.md)

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Docker**: 24.0+ | **Docker Compose**: v2.20+
