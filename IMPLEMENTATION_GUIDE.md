# Ultra PDF Chatbot 3000 - Detailed Implementation Guide

## 1. Django Project Setup

### 1.1 Project Structure
```
ultra_pdf_chatbot_3000/
├── chatbot/                 # Main Django app
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py        # Common settings
│   │   ├── development.py  # Dev-specific
│   │   └── production.py   # Prod-specific
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── chat/              # Chat interface app
│   │   ├── models.py      # Session, Message models
│   │   ├── views.py       # Chat views
│   │   ├── forms.py       # Upload forms
│   │   └── consumers.py   # WebSocket (optional)
│   ├── documents/         # Document processing
│   │   ├── models.py      # Document, Summary models
│   │   ├── parsers/       # PDF, Excel, Word parsers
│   │   ├── validators.py  # File validation
│   │   └── storage.py     # Custom storage backend
│   └── agents/            # SmolAgents integration
│       ├── tools/         # Custom tools
│       ├── orchestrator.py
│       └── registry.py
├── static/
│   ├── css/              # Tailwind build
│   ├── js/               # HTMX, Alpine.js
│   └── images/
├── templates/
│   ├── base.html         # Base template
│   ├── chat/             # Chat templates
│   └── components/       # Reusable HTMX components
├── media/                # User uploads (dev only)
├── tasks/                # Celery tasks
│   ├── __init__.py
│   ├── document_tasks.py
│   └── agent_tasks.py
├── tests/
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── manage.py
```

### 1.2 Dependencies (requirements/base.txt)
```txt
# Core
Django==5.0.1
python-decouple==3.8
django-environ==0.11.2

# Document Processing
PyPDF2==3.0.1
pdfplumber==0.10.3
pandas==2.1.4
openpyxl==3.1.2
XlsxWriter==3.1.9
python-docx==1.1.0
Pillow==10.2.0
matplotlib==3.8.2

# AI/Agents
smolagents==0.1.0
langchain==0.1.0
openai==1.6.1
tiktoken==0.5.2

# Async Processing
celery==5.3.4
redis==5.0.1
django-celery-beat==2.5.0
django-celery-results==2.5.1

# Frontend
django-htmx==1.17.2
django-widget-tweaks==1.5.0

# Security & Utils
django-cors-headers==4.3.1
django-ratelimit==4.1.0
python-magic==0.4.27
django-cleanup==8.0.0

# Production
gunicorn==21.2.0
whitenoise==6.6.0
psycopg2-binary==2.9.9
```

### 1.3 Initial Settings Configuration
```python
# settings/base.py
import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'django_htmx',
    'widget_tweaks',
    'django_celery_beat',
    'django_celery_results',
    'corsheaders',
    'django_cleanup.apps.CleanupConfig',
]

LOCAL_APPS = [
    'apps.chat',
    'apps.documents',
    'apps.agents',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'apps.documents.middleware.FileUploadValidationMiddleware',
]

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
FILE_UPLOAD_PERMISSIONS = 0o644

ALLOWED_FILE_EXTENSIONS = ['.pdf', '.xlsx', '.docx']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
MAX_DOCUMENTS_PER_SESSION = 20

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 7200  # 2 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Celery Configuration
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_TIME_LIMIT = 120  # 2 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 100  # Soft limit at 100 seconds
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50  # Restart worker after 50 tasks

# Temporary File Storage
TEMP_FILE_ROOT = Path('/tmp/ultra_pdf_chatbot')
TEMP_FILE_ROOT.mkdir(parents=True, exist_ok=True)
TEMP_FILE_CLEANUP_HOURS = 24

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'chatbot.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': config('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
```

## 2. Redis and Celery Configuration

### 2.1 Celery Application Setup
```python
# chatbot/celery.py
import os
from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')

app = Celery('chatbot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@setup_logging.connect
def config_loggers(loglevel, logfile, format, colorize, **kwargs):
    from django.conf import settings
    from logging.config import dictConfig
    dictConfig(settings.LOGGING)

# Task routing
app.conf.task_routes = {
    'tasks.document_tasks.*': {'queue': 'documents'},
    'tasks.agent_tasks.*': {'queue': 'agents'},
}

# Task rate limits
app.conf.task_annotations = {
    'tasks.document_tasks.process_large_file': {'rate_limit': '10/m'},
    'tasks.agent_tasks.run_agent_task': {'rate_limit': '30/m'},
}
```

### 2.2 Docker Compose for Development
```yaml
# docker/docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  celery_worker:
    build: .
    command: celery -A chatbot worker -l info -Q documents,agents,default
    volumes:
      - .:/app
      - /tmp/ultra_pdf_chatbot:/tmp/ultra_pdf_chatbot
    env_file:
      - .env
    depends_on:
      - redis
    restart: unless-stopped

  celery_beat:
    build: .
    command: celery -A chatbot beat -l info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      - redis
    restart: unless-stopped

  flower:
    build: .
    command: celery -A chatbot flower
    ports:
      - "5555:5555"
    env_file:
      - .env
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:
```

## 3. Django Models

### 3.1 Document Models
```python
# apps/documents/models.py
import uuid
from django.db import models
from django.contrib.sessions.models import Session
from django.core.validators import FileExtensionValidator
from django.conf import settings

class DocumentSession(models.Model):
    """Links documents to a browser session"""
    session = models.OneToOneField(Session, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    document_count = models.IntegerField(default=0)
    total_size = models.BigIntegerField(default=0)  # bytes
    
    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
        ]

class Document(models.Model):
    """Uploaded document model"""
    DOCUMENT_TYPES = [
        ('pdf', 'PDF Document'),
        ('xlsx', 'Excel Spreadsheet'),
        ('docx', 'Word Document'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(DocumentSession, on_delete=models.CASCADE, related_name='documents')
    original_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)  # Stored in temp directory
    document_type = models.CharField(max_length=10, choices=DOCUMENT_TYPES)
    file_size = models.BigIntegerField()  # bytes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Extracted content
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)  # Store extracted metadata
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['session', 'status']),
            models.Index(fields=['uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.original_name} ({self.get_status_display()})"

class DocumentContext(models.Model):
    """Aggregated context from all documents in a session"""
    session = models.OneToOneField(DocumentSession, on_delete=models.CASCADE)
    context_data = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)
    
    def update_context(self):
        """Rebuild context from all ready documents"""
        documents = self.session.documents.filter(status='ready')
        context = {
            'document_count': documents.count(),
            'documents': []
        }
        
        for doc in documents:
            context['documents'].append({
                'id': str(doc.id),
                'name': doc.original_name,
                'type': doc.document_type,
                'summary': doc.summary,
                'metadata': doc.metadata
            })
        
        self.context_data = context
        self.save()
```

### 3.2 Chat Models
```python
# apps/chat/models.py
import uuid
from django.db import models
from apps.documents.models import DocumentSession

class Conversation(models.Model):
    """Chat conversation linked to document session"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(DocumentSession, on_delete=models.CASCADE, related_name='conversations')
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']

class Message(models.Model):
    """Individual chat message"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For tracking async tasks
    task_id = models.CharField(max_length=255, blank=True)
    task_status = models.CharField(max_length=50, blank=True)
    
    # Attachments/results
    artifacts = models.JSONField(default=list)  # List of generated file IDs
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['task_id']),
        ]

class Artifact(models.Model):
    """Generated files from agent operations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='generated_artifacts')
    file_path = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # MIME type
    file_size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['expires_at']),
        ]
```

## 4. File Upload Validation

### 4.1 Validation Middleware
```python
# apps/documents/middleware.py
import magic
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

class FileUploadValidationMiddleware(MiddlewareMixin):
    """Validate file uploads before processing"""
    
    def process_request(self, request):
        if request.method == 'POST' and request.FILES:
            for field_name, uploaded_file in request.FILES.items():
                # Check file extension
                ext = os.path.splitext(uploaded_file.name)[1].lower()
                if ext not in settings.ALLOWED_FILE_EXTENSIONS:
                    return JsonResponse({
                        'error': f'File type {ext} not allowed. Allowed types: {", ".join(settings.ALLOWED_FILE_EXTENSIONS)}'
                    }, status=400)
                
                # Check file size
                if uploaded_file.size > settings.MAX_FILE_SIZE:
                    max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
                    return JsonResponse({
                        'error': f'File size exceeds maximum of {max_size_mb}MB'
                    }, status=400)
                
                # Verify MIME type
                mime = magic.from_buffer(uploaded_file.read(2048), mime=True)
                uploaded_file.seek(0)  # Reset file pointer
                
                allowed_mimes = {
                    '.pdf': ['application/pdf'],
                    '.xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
                    '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
                }
                
                if mime not in allowed_mimes.get(ext, []):
                    return JsonResponse({
                        'error': f'File content does not match extension {ext}'
                    }, status=400)
        
        return None
```

### 4.2 Custom Storage Backend
```python
# apps/documents/storage.py
import os
import hashlib
from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.crypto import get_random_string

class SessionFileStorage(FileSystemStorage):
    """Custom storage for session-based temporary files"""
    
    def __init__(self, session_id=None):
        self.session_id = session_id
        location = settings.TEMP_FILE_ROOT / 'sessions' / session_id if session_id else settings.TEMP_FILE_ROOT
        super().__init__(location=str(location))
    
    def get_unique_name(self, name):
        """Generate unique filename while preserving extension"""
        base, ext = os.path.splitext(name)
        random_str = get_random_string(8)
        return f"{base}_{random_str}{ext}"
    
    def save(self, name, content, max_length=None):
        """Save file with unique name"""
        name = self.get_unique_name(name)
        return super().save(name, content, max_length)
    
    def get_file_hash(self, file_path):
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
```

## 5. Document Parsing Tools

### 5.1 PDF Parser
```python
# apps/documents/parsers/pdf_parser.py
import logging
from typing import Dict, List, Any
import pdfplumber
import PyPDF2
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PDFContent:
    text: str
    tables: List[List[List[str]]]
    metadata: Dict[str, Any]
    page_count: int

class PDFParser:
    """Extract text and tables from PDF files"""
    
    @staticmethod
    def parse(file_path: str) -> PDFContent:
        """Parse PDF and extract content"""
        try:
            text_content = []
            tables = []
            metadata = {}
            
            # Extract text and tables with pdfplumber
            with pdfplumber.open(file_path) as pdf:
                metadata['page_count'] = len(pdf.pages)
                
                for page in pdf.pages:
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
                    
                    # Extract tables
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
            
            # Extract metadata with PyPDF2
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                if pdf_reader.metadata:
                    metadata.update({
                        'title': pdf_reader.metadata.get('/Title', ''),
                        'author': pdf_reader.metadata.get('/Author', ''),
                        'subject': pdf_reader.metadata.get('/Subject', ''),
                        'creator': pdf_reader.metadata.get('/Creator', ''),
                        'creation_date': str(pdf_reader.metadata.get('/CreationDate', '')),
                    })
            
            return PDFContent(
                text='\n'.join(text_content),
                tables=tables,
                metadata=metadata,
                page_count=metadata['page_count']
            )
            
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def generate_summary(content: PDFContent, max_length: int = 500) -> str:
        """Generate a summary of the PDF content"""
        summary_parts = []
        
        # Add basic info
        summary_parts.append(f"PDF Document with {content.page_count} pages")
        
        # Add metadata if available
        if content.metadata.get('title'):
            summary_parts.append(f"Title: {content.metadata['title']}")
        
        # Add table info
        if content.tables:
            summary_parts.append(f"Contains {len(content.tables)} tables")
        
        # Add text preview
        text_preview = content.text[:300].replace('\n', ' ')
        if text_preview:
            summary_parts.append(f"Preview: {text_preview}...")
        
        return ' | '.join(summary_parts)[:max_length]
```

### 5.2 Excel Parser
```python
# apps/documents/parsers/excel_parser.py
import pandas as pd
import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ExcelContent:
    sheets: Dict[str, pd.DataFrame]
    metadata: Dict[str, Any]
    summary_stats: Dict[str, Any]

class ExcelParser:
    """Parse and analyze Excel files"""
    
    @staticmethod
    def parse(file_path: str) -> ExcelContent:
        """Parse Excel file and extract all sheets"""
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            sheets = {}
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                sheets[sheet_name] = df
            
            # Generate metadata
            metadata = {
                'sheet_count': len(sheets),
                'sheet_names': excel_file.sheet_names,
                'total_rows': sum(len(df) for df in sheets.values()),
                'total_columns': sum(len(df.columns) for df in sheets.values()),
            }
            
            # Generate summary statistics for numeric columns
            summary_stats = {}
            for sheet_name, df in sheets.items():
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    summary_stats[sheet_name] = {
                        'numeric_columns': list(numeric_cols),
                        'summary': df[numeric_cols].describe().to_dict()
                    }
            
            return ExcelContent(
                sheets=sheets,
                metadata=metadata,
                summary_stats=summary_stats
            )
            
        except Exception as e:
            logger.error(f"Error parsing Excel {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def generate_summary(content: ExcelContent, max_length: int = 500) -> str:
        """Generate a summary of the Excel content"""
        summary_parts = []
        
        # Basic info
        summary_parts.append(
            f"Excel file with {content.metadata['sheet_count']} sheets, "
            f"{content.metadata['total_rows']} total rows"
        )
        
        # Sheet details
        for sheet_name, df in list(content.sheets.items())[:3]:  # First 3 sheets
            columns = list(df.columns)[:5]  # First 5 columns
            summary_parts.append(
                f"Sheet '{sheet_name}': {len(df)} rows, columns: {', '.join(map(str, columns))}"
            )
        
        return ' | '.join(summary_parts)[:max_length]
```

### 5.3 Word Parser
```python
# apps/documents/parsers/word_parser.py
import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

@dataclass
class WordContent:
    paragraphs: List[str]
    tables: List[List[List[str]]]
    headers: List[str]
    metadata: Dict[str, Any]

class WordParser:
    """Parse Word documents"""
    
    @staticmethod
    def parse(file_path: str) -> WordContent:
        """Parse Word document and extract content"""
        try:
            doc = Document(file_path)
            
            paragraphs = []
            tables = []
            headers = []
            
            # Extract paragraphs and headers
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)
                    
                    # Check if it's a heading
                    if para.style.name.startswith('Heading'):
                        headers.append(para.text)
            
            # Extract tables
            for table in doc.tables:
                table_data = []
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        row_data.append(cell.text.strip())
                    table_data.append(row_data)
                tables.append(table_data)
            
            # Extract metadata
            metadata = {
                'paragraph_count': len(paragraphs),
                'table_count': len(tables),
                'header_count': len(headers),
                'word_count': sum(len(p.split()) for p in paragraphs),
            }
            
            # Document properties
            core_props = doc.core_properties
            if core_props:
                metadata.update({
                    'title': core_props.title or '',
                    'author': core_props.author or '',
                    'subject': core_props.subject or '',
                    'created': str(core_props.created) if core_props.created else '',
                    'modified': str(core_props.modified) if core_props.modified else '',
                })
            
            return WordContent(
                paragraphs=paragraphs,
                tables=tables,
                headers=headers,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error parsing Word document {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def generate_summary(content: WordContent, max_length: int = 500) -> str:
        """Generate a summary of the Word content"""
        summary_parts = []
        
        # Basic info
        summary_parts.append(
            f"Word document with {content.metadata['paragraph_count']} paragraphs, "
            f"{content.metadata['word_count']} words"
        )
        
        # Add title if available
        if content.metadata.get('title'):
            summary_parts.append(f"Title: {content.metadata['title']}")
        
        # Add headers preview
        if content.headers:
            headers_preview = ', '.join(content.headers[:3])
            summary_parts.append(f"Headers: {headers_preview}")
        
        # Add text preview
        if content.paragraphs:
            text_preview = ' '.join(content.paragraphs[:2])[:200]
            summary_parts.append(f"Preview: {text_preview}...")
        
        return ' | '.join(summary_parts)[:max_length]
```

## 6. Chart Generation Tool

```python
# apps/agents/tools/chart_generator.py
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import io
import base64
from typing import Dict, Any, Optional, List
from pathlib import Path
import uuid

class ChartGenerator:
    """Generate charts using matplotlib"""
    
    CHART_TYPES = ['bar', 'line', 'pie', 'scatter', 'histogram', 'area']
    
    @staticmethod
    def generate_chart(
        data: Dict[str, Any],
        chart_type: str = 'bar',
        title: str = '',
        xlabel: str = '',
        ylabel: str = '',
        save_path: Optional[str] = None
    ) -> str:
        """
        Generate a chart from data specification
        
        Args:
            data: Dictionary with 'x' and 'y' keys for data
            chart_type: Type of chart to generate
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            save_path: Optional path to save the chart
            
        Returns:
            Path to saved chart image
        """
        
        if chart_type not in ChartGenerator.CHART_TYPES:
            