#!/usr/bin/env python3
"""
Verification script for Ultra PDF Chatbot 3000 project structure
"""
import os
from pathlib import Path

def verify_structure():
    """Verify that all required files and directories exist"""
    base_dir = Path(__file__).parent
    
    required_files = [
        'manage.py',
        'chatbot/__init__.py',
        'chatbot/settings/__init__.py',
        'chatbot/settings/base.py',
        'chatbot/settings/development.py',
        'chatbot/settings/production.py',
        'chatbot/urls.py',
        'chatbot/wsgi.py',
        'chatbot/asgi.py',
        'chatbot/celery.py',
        'apps/__init__.py',
        'apps/chat/__init__.py',
        'apps/chat/apps.py',
        'apps/chat/models.py',
        'apps/chat/views.py',
        'apps/chat/urls.py',
        'apps/documents/__init__.py',
        'apps/documents/apps.py',
        'apps/documents/models.py',
        'apps/documents/views.py',
        'apps/documents/urls.py',
        'apps/documents/middleware.py',
        'apps/documents/validators.py',
        'apps/documents/storage.py',
        'apps/documents/parsers/__init__.py',
        'apps/agents/__init__.py',
        'apps/agents/apps.py',
        'apps/agents/models.py',
        'apps/agents/views.py',
        'apps/agents/urls.py',
        'apps/agents/orchestrator.py',
        'apps/agents/registry.py',
        'apps/agents/tools/__init__.py',
        'tasks/__init__.py',
        'tasks/document_tasks.py',
        'tasks/agent_tasks.py',
        'requirements/base.txt',
        'requirements/development.txt',
        'requirements/production.txt',
        'docker/docker-compose.yml',
        'templates/base.html',
        '.env.example',
        '.env',
    ]
    
    required_dirs = [
        'static/css',
        'static/js',
        'static/images',
        'templates/chat',
        'templates/components',
        'media',
        'logs',
        'tests',
    ]
    
    print("Verifying Ultra PDF Chatbot 3000 project structure...")
    print("=" * 60)
    
    missing_files = []
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path}")
            missing_files.append(file_path)
    
    missing_dirs = []
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"✓ {dir_path}/")
        else:
            print(f"✗ {dir_path}/")
            missing_dirs.append(dir_path)
    
    print("=" * 60)
    if not missing_files and not missing_dirs:
        print("✅ All required files and directories are present!")
        print("🚀 Project structure setup is complete!")
        return True
    else:
        if missing_files:
            print(f"❌ Missing files: {missing_files}")
        if missing_dirs:
            print(f"❌ Missing directories: {missing_dirs}")
        return False

if __name__ == "__main__":
    verify_structure()