#!/bin/bash
set -e

echo "Starting Django application..."

# Wait for database to be ready (if using external database)
echo "Waiting for database..."
python manage.py check --database default

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start the Django development server
echo "Starting Django server..."
exec python manage.py runserver 0.0.0.0:8000