# Docker Setup for Ultra PDF Chatbot 3000

## Overview
This Docker configuration provides a complete containerized environment for the Ultra PDF Chatbot 3000 Django application.

## Files Created
- `Dockerfile` - Main application container definition
- `docker-entrypoint.sh` - Startup script for migrations and setup
- `.dockerignore` - Optimizes build by excluding unnecessary files
- `docker/docker-compose.yml` - Complete orchestration with all services

## Services Included
- **web** - Django application (port 8000)
- **db** - PostgreSQL 15 database (port 5432)
- **redis** - Redis cache and message broker (port 6379)
- **celery_worker** - Background task processing
- **celery_beat** - Scheduled task processing
- **flower** - Celery monitoring (port 5555)

## Quick Start

1. **Build and start all services:**
   ```bash
   cd docker
   docker-compose up --build
   ```

2. **Run in background:**
   ```bash
   docker-compose up -d --build
   ```

3. **View logs:**
   ```bash
   docker-compose logs -f web
   ```

4. **Access the application:**
   - Main app: http://localhost:8000
   - Admin: http://localhost:8000/admin (admin/admin123)
   - Flower monitoring: http://localhost:5555

## Environment Variables
Create a `.env` file in the root directory with:
```
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
OPENAI_API_KEY=your-openai-api-key
```

## Production Notes
- The Dockerfile uses production dependencies
- Non-root user for security
- Health checks included
- Automatic migrations on startup
- Static files collection handled automatically

## Commands
```bash
# Stop all services
docker-compose down

# Rebuild specific service
docker-compose build web

# Run Django commands
docker-compose exec web python manage.py shell

# View database
docker-compose exec db psql -U postgres -d chatbot