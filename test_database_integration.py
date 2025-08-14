#!/usr/bin/env python3
"""
Test script to verify database integration and artifact display
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django BEFORE importing any Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
import django
django.setup()

# Now import Django models and our components
from django.test import TestCase
from django.contrib.sessions.models import Session
from apps.agents.orchestrator import ChatbotOrchestrator
from apps.documents.models import DocumentSession
from apps.chat.models import Conversation, Message, Artifact

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_test_session():
    """Create a test session and related objects"""
    from django.utils import timezone
    from datetime import timedelta
    
    # Create Django session with proper expire_date
    session = Session.objects.create(
        session_key='test_session_key',
        session_data='{}',
        expire_date=timezone.now() + timedelta(days=1)
    )
    
    # Create document session
    doc_session = DocumentSession.objects.create(session=session)
    
    # Create conversation
    conversation = Conversation.objects.create(session=doc_session)
    
    # Create test message
    message = Message.objects.create(
        conversation=conversation,
        role='assistant',
        content='Test message for artifact generation'
    )
    
    return session, doc_session, conversation, message

def create_test_files():
    """Create test files to simulate tool outputs"""
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    test_files = [
        'temp/db_test_excel.xlsx',
        'temp/db_test_document.docx',
        'temp/db_test_chart.png'
    ]
    
    # Create actual files with some content
    for file_path in test_files:
        with open(file_path, 'wb') as f:
            f.write(b'test content for database integration')
        logger.info(f"Created test file: {file_path}")
    
    return test_files

def test_artifact_database_creation():
    """Test that artifacts are properly created in the database"""
    logger.info("=== Testing Artifact Database Creation ===")
    
    try:
        # Create test session and objects
        session, doc_session, conversation, message = create_test_session()
        
        # Create test files
        test_files = create_test_files()
        
        # Initialize orchestrator
        orchestrator = ChatbotOrchestrator(session_id=session.session_key)
        
        # Create artifact data
        artifacts_data = []
        for file_path in test_files:
            artifacts_data.append({
                'type': 'file',
                'path': file_path,
                'name': Path(file_path).name
            })
        
        # Test artifact record creation
        initial_count = Artifact.objects.count()
        orchestrator._create_artifact_records(artifacts_data, message)
        final_count = Artifact.objects.count()
        
        created_count = final_count - initial_count
        logger.info(f"Created {created_count} artifact records in database")
        
        # Verify artifacts in database
        message_artifacts = message.generated_artifacts.all()
        logger.info(f"Message has {message_artifacts.count()} associated artifacts")
        
        for artifact in message_artifacts:
            logger.info(f"  - {artifact.file_name} ({artifact.file_type}) - {artifact.file_size} bytes")
            
            # Verify file exists
            if Path(artifact.file_path).exists():
                logger.info(f"    ✓ File exists: {artifact.file_path}")
            else:
                logger.warning(f"    ✗ File missing: {artifact.file_path}")
        
        # Clean up
        cleanup_test_data(session, test_files)
        
        return created_count > 0 and message_artifacts.count() > 0
        
    except Exception as e:
        logger.error(f"Database creation test failed: {e}", exc_info=True)
        return False

def test_full_orchestrator_flow():
    """Test the full orchestrator flow with database integration"""
    logger.info("=== Testing Full Orchestrator Flow ===")
    
    try:
        # Create test session and objects
        session, doc_session, conversation, message = create_test_session()
        
        # Initialize orchestrator
        orchestrator = ChatbotOrchestrator(session_id=session.session_key)
        
        # Simulate CodeAgent result that should generate artifacts
        mock_result = """
        Excel file created successfully: temp/flow_test_report.xlsx
        Document saved to: temp/flow_test_summary.docx
        Chart generated successfully: temp/flow_test_chart.png
        """
        
        # Create the files that the mock result references
        test_files = [
            'temp/flow_test_report.xlsx',
            'temp/flow_test_summary.docx', 
            'temp/flow_test_chart.png'
        ]
        
        for file_path in test_files:
            with open(file_path, 'wb') as f:
                f.write(b'test content for full flow test')
        
        # Get filesystem snapshots
        temp_dir = os.path.join(os.getcwd(), 'temp')
        files_before = orchestrator._get_temp_files_snapshot(temp_dir)
        
        # Add the test files to simulate "after" state
        files_after = orchestrator._get_temp_files_snapshot(temp_dir)
        
        # Test enhanced extraction
        artifacts = orchestrator._extract_artifacts_enhanced(mock_result, files_before, files_after)
        logger.info(f"Enhanced extraction found: {len(artifacts)} artifacts")
        
        # Test database creation
        initial_count = Artifact.objects.count()
        orchestrator._create_artifact_records(artifacts, message)
        final_count = Artifact.objects.count()
        
        created_count = final_count - initial_count
        logger.info(f"Full flow created {created_count} artifact records")
        
        # Verify results
        message_artifacts = message.generated_artifacts.all()
        for artifact in message_artifacts:
            logger.info(f"  - {artifact.file_name} ({artifact.file_type})")
        
        # Clean up
        cleanup_test_data(session, test_files)
        
        return created_count > 0
        
    except Exception as e:
        logger.error(f"Full flow test failed: {e}", exc_info=True)
        return False

def cleanup_test_data(session, test_files):
    """Clean up test data"""
    try:
        # Delete test files
        for file_path in test_files:
            if Path(file_path).exists():
                os.remove(file_path)
                logger.debug(f"Cleaned up test file: {file_path}")
        
        # Delete test database objects
        DocumentSession.objects.filter(session=session).delete()
        session.delete()
        logger.debug("Cleaned up test database objects")
        
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")

def main():
    """Run all database integration tests"""
    logger.info("Starting database integration tests...")
    
    results = []
    
    try:
        # Test 1: Artifact database creation
        results.append(("Artifact Database Creation", test_artifact_database_creation()))
        
        # Test 2: Full orchestrator flow
        results.append(("Full Orchestrator Flow", test_full_orchestrator_flow()))
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        results.append(("Test Execution", False))
    
    # Report results
    logger.info("=== Database Integration Test Results ===")
    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("All database integration tests passed!")
    else:
        logger.error("Some database integration tests failed.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)