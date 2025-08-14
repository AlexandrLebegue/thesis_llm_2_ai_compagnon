#!/usr/bin/env python
"""
Test script to verify the connection between uploaded files and LLM agent
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

from django.contrib.sessions.models import Session
from apps.documents.models import DocumentSession, Document
from apps.documents.storage import SessionFileStorage
from apps.agents.orchestrator import ChatbotOrchestrator
from apps.agents.tools.parse_pdf_tool import ParsePDFTool
import logging
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pdf_connection():
    """Test the complete PDF upload and processing chain"""
    print("=" * 60)
    print("Testing PDF connection between upload and LLM agent")
    print("=" * 60)
    
    # Step 1: Create a test session
    print("\n1. Creating test session...")
    test_session_key = "test_session_123"
    
    # Create session properly with required fields
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        session_obj = Session.objects.get(session_key=test_session_key)
    except Session.DoesNotExist:
        session_obj = Session.objects.create(
            session_key=test_session_key,
            session_data={},
            expire_date=timezone.now() + timedelta(days=1)
        )
    
    doc_session, created = DocumentSession.objects.get_or_create(session=session_obj)
    print(f"✓ Session created: {test_session_key}")
    
    # Step 2: Check if we have any existing files
    print("\n2. Looking for test files...")
    test_files_dir = Path("test_files")
    docx_files = list(test_files_dir.glob("*.docx")) if test_files_dir.exists() else []
    
    if not docx_files:
        print("⚠ No DOCX files found in test_files directory")
        print("Creating a mock document entry...")
        # Create a mock document entry for testing
        document = Document.objects.create(
            session=doc_session,
            original_name="sample.docx",
            file_path="sample.docx",
            document_type="docx",
            file_size=1024,
            status="ready"
        )
        test_filename = "sample.docx"
        test_type = "docx"
    else:
        test_docx = docx_files[0]
        print(f"✓ Found test DOCX: {test_docx}")
        test_filename = test_docx.name
        test_type = "docx"
        
        # Copy the file to session storage to simulate upload
        print("✓ Copying file to session storage...")
        from apps.documents.storage import SessionFileStorage
        import shutil
        
        storage = SessionFileStorage(session_id=test_session_key)
        
        # Copy the test file to session storage
        dest_path = storage.path(test_filename)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(test_docx, dest_path)
        
        # Create document record
        document = Document.objects.create(
            session=doc_session,
            original_name=test_filename,
            file_path=test_filename,
            document_type=test_type,
            file_size=test_docx.stat().st_size,
            status="ready"
        )
        print(f"✓ File copied to: {dest_path}")
    
    # Step 3: Test direct Word parser tool
    print(f"\n3. Testing Word parser tool with session context...")
    from apps.agents.tools.parse_word_tool import ParseWordTool
    word_tool = ParseWordTool(session_id=test_session_key)
    
    try:
        result = word_tool.forward(test_filename)
        print(f"✓ Word Parser result status: {result.get('status')}")
        if result.get('status') == 'error':
            print(f"✗ Word Parser error: {result.get('error')}")
        else:
            print(f"✓ Word parsed successfully")
            print(f"  - Text length: {len(result.get('text', ''))}")
            print(f"  - Tables found: {len(result.get('tables', []))}")
            print(f"  - Headers found: {len(result.get('headers', []))}")
            print(f"  - Metadata: {result.get('metadata', {})}")
    except Exception as e:
        print(f"✗ Word Parser exception: {str(e)}")
    
    # Step 4: Test orchestrator
    print(f"\n4. Testing orchestrator with session context...")
    try:
        orchestrator = ChatbotOrchestrator(session_id=test_session_key)
        print("✓ Orchestrator created successfully")
        
        # Build test context
        context = {
            'documents': [{
                'name': test_filename,
                'type': test_type,
                'summary': f'Test {test_type.upper()} document: {test_filename}'
            }]
        }
        
        print("✓ Test context built")
        
        # Test a simple request
        instruction = f"Analyze the content of {test_filename}"
        print(f"✓ Testing instruction: {instruction}")
        
        result = orchestrator.process_request(
            instruction=instruction,
            context=context,
            session_id=test_session_key
        )
        
        print(f"✓ Orchestrator result status: {result.get('status')}")
        if result.get('status') == 'error':
            print(f"✗ Orchestrator error: {result.get('error')}")
        else:
            print(f"✓ Orchestrator processed successfully")
            print(f"  - Result: {str(result.get('result', ''))[:200]}...")
            
    except Exception as e:
        print(f"✗ Orchestrator exception: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Step 5: Test file path resolution
    print(f"\n5. Testing file path resolution...")
    storage = SessionFileStorage(session_id=test_session_key)
    print(f"✓ Session storage path: {storage.base_path}")
    print(f"✓ Storage exists: {storage.base_path.exists()}")
    
    # List files in storage
    if storage.base_path.exists():
        files = list(storage.base_path.glob("*"))
        print(f"✓ Files in storage: {[f.name for f in files]}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
    
    # Cleanup
    try:
        # Clean up test data
        doc_session.documents.all().delete()
        doc_session.delete()
        session_obj.delete()
        print("✓ Test data cleaned up")
    except Exception as e:
        print(f"⚠ Cleanup warning: {str(e)}")

if __name__ == "__main__":
    test_pdf_connection()