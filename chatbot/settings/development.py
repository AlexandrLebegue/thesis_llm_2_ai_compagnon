from .base import *

# Development specific settings
DEBUG = True

# Get allowed hosts from environment variable, fallback to development defaults
import os
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1],0.0.0.0').split(',')

# CSRF trusted origins for development (including Cloud Run URLs)
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if os.environ.get('CSRF_TRUSTED_ORIGINS') else ["https://thesis-llm-2-881860961470.europe-west1.run.app"]

# Development database (SQLite)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development middleware (add debug toolbar if available)
try:
    import debug_toolbar
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
except ImportError:
    pass

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Static files for development
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Celery settings for development
CELERY_TASK_ALWAYS_EAGER = False  # Set to True to run tasks synchronously
CELERY_TASK_EAGER_PROPAGATES = True

# Security settings (relaxed for development)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Additional development apps
# Temporarily disabled until dependencies are installed
# INSTALLED_APPS += [
#     'django_extensions',
# ]

# Media files served by Django in development
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'