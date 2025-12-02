# ============================================
# QUICK REFERENCE: Docker Commands
# ============================================

# BUILD & START
# ============================================
# Build all images
docker-compose build

# Build without cache (fresh build)
docker-compose build --no-cache

# Start all services (detached mode)
docker-compose up -d

# Start with logs visible
docker-compose up

# Build and start together
docker-compose up -d --build


# SERVICE MANAGEMENT
# ============================================
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data!)
docker-compose down -v

# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart django
docker-compose restart fastapi

# Stop specific service
docker-compose stop django


# LOGS & MONITORING
# ============================================
# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f django
docker-compose logs -f fastapi
docker-compose logs -f db

# View last 100 lines
docker-compose logs --tail=100 django

# Check service status
docker-compose ps

# View resource usage
docker stats


# EXECUTE COMMANDS IN CONTAINERS
# ============================================
# Django commands
docker-compose exec django python manage.py migrate
docker-compose exec django python manage.py createsuperuser
docker-compose exec django python manage.py collectstatic --noinput
docker-compose exec django python manage.py shell

# FastAPI commands
docker-compose exec fastapi python init_db.py
docker-compose exec fastapi python app/ingestion/ingest_platform_docs.py

# Database access
docker-compose exec db psql -U nlp_admin -d nlp_platform

# Redis access
docker-compose exec redis redis-cli -a redis123

# Shell access
docker-compose exec django bash
docker-compose exec fastapi bash


# DATABASE OPERATIONS
# ============================================
# Backup database
docker-compose exec db pg_dump -U nlp_admin nlp_platform > backup.sql

# Restore database
cat backup.sql | docker-compose exec -T db psql -U nlp_admin nlp_platform

# Reset database (WARNING: deletes all data!)
docker-compose down -v
docker-compose up -d db
sleep 10
docker-compose exec db psql -U nlp_admin -d nlp_platform -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker-compose up -d


# IMAGE MANAGEMENT
# ============================================
# List images
docker images

# Remove image
docker rmi plateforme_nlp-django
docker rmi plateforme_nlp-fastapi

# Save images to file
docker save -o nlp_images.tar plateforme_nlp-django plateforme_nlp-fastapi

# Load images from file
docker load -i nlp_images.tar

# Remove unused images
docker image prune -a


# VOLUME MANAGEMENT
# ============================================
# List volumes
docker volume ls

# Inspect volume
docker volume inspect plateforme_nlp_postgres_data

# Remove all unused volumes
docker volume prune


# NETWORK OPERATIONS
# ============================================
# List networks
docker network ls

# Inspect network
docker network inspect plateforme_nlp_nlp_network

# Test connectivity between services
docker-compose exec django ping db
docker-compose exec django ping fastapi


# CLEANUP
# ============================================
# Remove all stopped containers
docker container prune

# Remove all unused resources
docker system prune

# Remove everything including volumes (DANGEROUS!)
docker system prune -a --volumes


# TROUBLESHOOTING
# ============================================
# Check service health
docker-compose ps

# Follow logs in real-time
docker-compose logs -f --tail=50

# Restart specific service with logs
docker-compose restart django && docker-compose logs -f django

# Check port binding
netstat -ano | findstr :80     # Windows
lsof -i :80                     # Linux/Mac

# Inspect container
docker inspect nlp_django

# Check environment variables
docker-compose exec django env


# PRODUCTION DEPLOYMENT
# ============================================
# Save images for offline deployment
docker save -o nlp_images.tar \
  plateforme_nlp-django:latest \
  plateforme_nlp-fastapi:latest \
  ankane/pgvector:latest \
  redis:7-alpine \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0 \
  nginx:1.25-alpine

# Compress images
gzip nlp_images.tar

# Load on production server
gunzip -c nlp_images.tar.gz | docker load


# USEFUL COMBINATIONS
# ============================================
# Complete restart with fresh build
docker-compose down && docker-compose build && docker-compose up -d

# View all logs since last restart
docker-compose logs --since 10m

# Check if services are responding
curl http://localhost/
curl http://localhost/api/health

# Emergency stop
docker-compose kill
docker-compose down


# DEVELOPMENT WORKFLOW
# ============================================
# 1. Start development environment
docker-compose up -d

# 2. Run migrations after model changes
docker-compose exec django python manage.py makemigrations
docker-compose exec django python manage.py migrate

# 3. Create new Django app
docker-compose exec django python manage.py startapp myapp

# 4. Collect static files
docker-compose exec django python manage.py collectstatic --noinput

# 5. Test FastAPI endpoints
curl http://localhost/api/health
curl http://localhost/api/docs


# MONITORING & HEALTH CHECKS
# ============================================
# Check all services are healthy
docker-compose ps | grep "healthy"

# Test each service
curl -f http://localhost/ || echo "Django failed"
curl -f http://localhost/api/health || echo "FastAPI failed"
docker-compose exec db pg_isready -U nlp_admin || echo "Database failed"
docker-compose exec redis redis-cli -a redis123 ping || echo "Redis failed"
curl -f http://localhost:9200/_cluster/health || echo "Elasticsearch failed"


# SECURITY CHECKS
# ============================================
# Scan images for vulnerabilities
docker scan plateforme_nlp-django
docker scan plateforme_nlp-fastapi

# Check running processes inside container
docker-compose exec django ps aux

# Verify non-root user
docker-compose exec django whoami  # Should return "django" not "root"
docker-compose exec fastapi whoami  # Should return "fastapi" not "root"
