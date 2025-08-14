# Use the official Python runtime image
FROM python:3.13  
 
# Create the app directory
RUN mkdir /app

# Set the working directory inside the container
WORKDIR /app

# Create necessary directories for Django with proper permissions
RUN mkdir -p /app/logs /app/media /app/staticfiles /app/temp && \
    chmod 755 /app/logs /app/media /app/staticfiles /app/temp
 
# Set environment variables 
# Prevents Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 
#Prevents Python from buffering stdout and stderr
ENV DEBUG=True
ENV SECRET_KEY=$SECRET_KEY
ENV REDIS_URL=redis://localhost:6379/0
ENV DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,[::1],0.0.0.0,*
ENV OPENROUTER_API_KEY=$OPENROUTER_API_KEY 
ENV DJANGO_LOG_LEVEL=INFO
# Upgrade pip
RUN pip install --upgrade pip 
 
# Copy the Django project  and install dependencies
COPY requirements.txt  /app/
 
# run this command to install all dependencies 
RUN pip install --no-cache-dir -r requirements.txt
# RUN pip install --no-cache-dir -r production.txt
 
# Copy the Django project to the container
COPY . /app/

# Copy and set permissions for entrypoint script
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Expose the Django port
EXPOSE 8000

# Set the entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]