# Docker Usage Instructions for Ultra PDF Chatbot 3000

## ✅ Issue Fixed

Your Docker connectivity issue has been resolved! The problem was:

1. **Missing Port Mapping**: Container was running without `-p 8000:8000` flag
2. **ALLOWED_HOSTS Configuration**: Django settings didn't include `0.0.0.0` and `*` for Docker networking
3. **Environment Variables**: Not properly configured for Docker environment

## 🐳 How to Run Your Application

### Option 1: Simple Docker Run (Recommended for Development)

```bash
# Build the image (only needed when code changes)
docker build -t django-chatbot .

# Run with proper port mapping
docker run -d -p 8000:8000 --env-file .env django-chatbot

# Access your application at:
# http://localhost:8000
```

### Option 2: Docker Compose (Recommended for Production)

```bash
# Navigate to docker directory
cd docker

# Start all services (web, database, redis, celery)
docker-compose up -d --build

# Access your application at:
# http://localhost:8000
# Flower monitoring: http://localhost:5555
```

## 🔧 Common Docker Commands

```bash
# View running containers
docker ps

# View container logs
docker logs <container_id>

# Stop container
docker stop <container_id>

# Remove container
docker rm <container_id>

# Remove image
docker rmi django-chatbot

# Stop all services (docker-compose)
docker-compose down

# View service logs
docker-compose logs -f web
```

## 🌐 Network Access

Your Django application is now accessible at:
- **localhost:8000** - Main application
- **127.0.0.1:8000** - Alternative local access
- **0.0.0.0:8000** - All network interfaces (within container)

## 🔧 Configuration Updates Made

### 1. Updated `chatbot/settings/development.py`
```python
# Now reads ALLOWED_HOSTS from environment variable
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1],0.0.0.0').split(',')
```

### 2. Updated `.env` file
```env
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],0.0.0.0,*
```

### 3. Updated `Dockerfile`
```dockerfile
ENV DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],0.0.0.0,*
```

## 🚀 Current Status

✅ Container is running with proper port mapping: `0.0.0.0:8000->8000/tcp`  
✅ Django server started successfully  
✅ Database migrations completed  
✅ Static files collected  
✅ Application accessible at http://localhost:8000  

## 🔍 Troubleshooting

If you still can't connect:

1. **Check if port 8000 is available:**
   ```bash
   netstat -an | grep 8000
   ```

2. **Verify Docker port mapping:**
   ```bash
   docker ps
   # Should show: 0.0.0.0:8000->8000/tcp
   ```

3. **Check container logs:**
   ```bash
   docker logs <container_id>
   ```

4. **Test connectivity:**
   ```bash
   curl http://localhost:8000
   ```

## 💡 Development Tips

- Use `docker-compose` for full development environment with database and Redis
- Use `docker run` for quick testing of the Django application only
- Always include `-p 8000:8000` flag when using `docker run`
- Environment variables in `.env` file are automatically loaded
- Container automatically runs migrations and collects static files on startup

Your Django application is now properly containerized and accessible!