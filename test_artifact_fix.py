#!/usr/bin/env python3
"""
Test script to verify the artifact registration fix.

This script tests that parsing tools now properly register artifacts
for data previews and downloads.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

from apps.agents.tools.parse_excel_tool import ParseExcelTool
from apps.agents.tools.parse_word_tool import ParseWordTool
from apps.agents.orchestrator import ChatbotOrchestrator
from apps.documents.models import DocumentSession, Document
from apps.chat.models import Conversation, Message
from django.contrib.sessions.models import Session
from django.utils import timezone
import tempfile
import pandas as pd
import json

def create_test_excel():
    """Create a test Excel file for testing"""
    # Create temporary Excel file
    test_data = {
        'Product': ['Widget A', 'Widget B', 'Widget C'],
        'Sales': [100, 150, 200],
        'Region': ['North', 'South', 'East']
    }
    df = pd.DataFrame(test_data)
    
    temp_dir = Path.cwd() / 'temp' / 'test'
    temp_dir.mkdir(parents=True, exist_ok=True)
    excel_path = temp_dir / 'test_data.xlsx'
    
    df.to_excel(excel_path, index=False)
    return str(excel_path)

def test_excel_parsing_artifacts():
    """Test that Excel parsing creates downloadable artifacts"""
    print("🧪 Testing Excel parsing artifact generation...")
    
    # Create test Excel file
    excel_path = create_test_excel()
    print(f"📄 Created test Excel: {excel_path}")
    
    # Initialize Excel parser
    parser = ParseExcelTool()
    
    # Parse the Excel file
    result = parser.forward(excel_path)
    
    # Verify result structure
    print(f"📊 Parse result status: {result.get('status')}")
    print(f"🗂️  Number of sheets: {len(result.get('sheets', {}))}")
    
    # Check for artifacts
    artifacts = result.get('artifacts', [])
    print(f"📎 Generated artifacts: {len(artifacts)}")
    
    for i, artifact in enumerate(artifacts):
        artifact_path = Path(artifact['path'])
        exists = artifact_path.exists()
        size = artifact_path.stat().st_size if exists else 0
        print(f"  {i+1}. {artifact['name']} ({artifact['type']}) - {'✓' if exists else '✗'} ({size} bytes)")
    
    return len(artifacts) > 0

def test_orchestrator_artifact_extraction():
    """Test that orchestrator properly extracts artifacts from parsing results"""
    print("\n🎭 Testing orchestrator artifact extraction...")
    
    # Create mock result from parsing tool
    mock_result = {
        'status': 'success',
        'sheets': {'Sheet1': [{'A': 1, 'B': 2}]},
        'artifacts': [
            {
                'type': 'data_preview',
                'path': str(Path.cwd() / 'temp' / 'test' / 'test_preview.csv'),
                'name': 'Test Preview'
            }
        ],
        'generated_files': [
            str(Path.cwd() / 'temp' / 'test' / 'test_file.csv')
        ]
    }
    
    # Create test files
    for file_path in [mock_result['artifacts'][0]['path']] + mock_result['generated_files']:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text("test,data\n1,2")
    
    # Initialize orchestrator
    try:
        orchestrator = ChatbotOrchestrator()
        
        # Test artifact extraction
        extracted_artifacts = orchestrator._extract_artifacts(mock_result)
        
        print(f"📦 Extracted artifacts: {len(extracted_artifacts)}")
        for artifact in extracted_artifacts:
            print(f"  - {artifact['name']} ({artifact['type']}) at {artifact['path']}")
        
        return len(extracted_artifacts) > 0
        
    except Exception as e:
        print(f"❌ Orchestrator test failed: {e}")
        return False

def test_full_workflow():
    """Test the complete workflow from parsing to artifact registration"""
    print("\n🔄 Testing full workflow...")
    
    try:
        # Create test session with proper expire_date
        from datetime import datetime, timedelta
        session_obj = Session.objects.create(
            session_key='test_session_123',
            expire_date=timezone.now() + timedelta(days=1)
        )
        doc_session = DocumentSession.objects.create(session=session_obj)
        conversation = Conversation.objects.create(session=doc_session)
        
        # Create test message
        message = Message.objects.create(
            conversation=conversation,
            role='user',
            content='Parse test data'
        )
        
        # Create assistant message for response
        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Processing...',
            artifacts=[]
        )
        
        # Create test Excel and parse it
        excel_path = create_test_excel()
        parser = ParseExcelTool(session_id='test_session_123')
        result = parser.forward(excel_path)
        
        # Extract artifacts using orchestrator
        orchestrator = ChatbotOrchestrator(session_id='test_session_123')
        artifacts = orchestrator._extract_artifacts(result)
        
        # Create artifact records
        orchestrator._create_artifact_records(artifacts, assistant_message)
        
        # Check if artifacts were registered
        from apps.chat.models import Artifact
        registered_artifacts = Artifact.objects.filter(message=assistant_message)
        
        print(f"💾 Registered artifacts in database: {registered_artifacts.count()}")
        for artifact in registered_artifacts:
            print(f"  - {artifact.file_name} ({artifact.file_type}) - {artifact.file_size} bytes")
        
        success = registered_artifacts.count() > 0
        
        # Cleanup
        registered_artifacts.delete()
        conversation.delete()
        doc_session.delete()
        session_obj.delete()
        
        return success
        
    except Exception as e:
        print(f"❌ Full workflow test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting artifact registration fix tests...\n")
    
    tests = [
        ("Excel Parsing Artifacts", test_excel_parsing_artifacts),
        ("Orchestrator Extraction", test_orchestrator_artifact_extraction),
        ("Full Workflow", test_full_workflow)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"{'✅' if success else '❌'} {test_name}: {'PASS' if success else 'FAIL'}\n")
        except Exception as e:
            results.append((test_name, False))
            print(f"❌ {test_name}: FAIL - {e}\n")
    
    # Summary
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The artifact registration fix is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)