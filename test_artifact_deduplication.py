#!/usr/bin/env python3
"""
Test script for artifact deduplication improvements

This script tests the enhanced artifact detection and deduplication logic
to ensure the document preview duplication issue is resolved.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

from apps.agents.orchestrator import ChatbotOrchestrator
from apps.chat.models import Conversation, Message, Artifact
from apps.documents.models import DocumentSession
from django.contrib.sessions.models import Session

class ArtifactDeduplicationTests:
    """Test suite for artifact deduplication functionality"""
    
    def __init__(self):
        self.test_session_id = "test_artifact_dedup_session"
        self.temp_dir = None
        self.orchestrator = None
        
    def setup(self):
        """Setup test environment"""
        print("Setting up test environment...")
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp(prefix="artifact_test_")
        print(f"Created temp directory: {self.temp_dir}")
        
        # Create orchestrator instance
        self.orchestrator = ChatbotOrchestrator(session_id=self.test_session_id)
        
        # Create test session and conversation with proper expire_date
        from django.utils import timezone
        from datetime import timedelta
        
        session_obj, _ = Session.objects.get_or_create(
            session_key=self.test_session_id,
            defaults={'expire_date': timezone.now() + timedelta(days=1)}
        )
        doc_session, _ = DocumentSession.objects.get_or_create(session=session_obj)
        self.conversation, _ = Conversation.objects.get_or_create(session=doc_session)
        
        print("Test environment setup complete")
        
    def cleanup(self):
        """Cleanup test environment"""
        print("Cleaning up test environment...")
        
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"Removed temp directory: {self.temp_dir}")
            
        # Clean up database objects
        try:
            Artifact.objects.filter(message__conversation=self.conversation).delete()
            Message.objects.filter(conversation=self.conversation).delete()
            self.conversation.delete()
            print("Cleaned up database objects")
        except Exception as e:
            print(f"Database cleanup warning: {e}")
            
    def create_test_files(self, file_specs):
        """Create test files with specified content"""
        created_files = {}
        
        for filename, content in file_specs.items():
            file_path = os.path.join(self.temp_dir, filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            created_files[filename] = file_path
            
        return created_files
        
    def test_path_normalization(self):
        """Test path normalization in deduplication"""
        print("\n=== Testing Path Normalization ===")
        
        # Create test files with different path representations
        test_files = {
            'test_doc.xlsx': 'Test Excel content',
            'subdir/another_doc.docx': 'Test Word content'
        }
        
        created_files = self.create_test_files(test_files)
        
        # Create artifacts with different path formats
        artifacts = [
            {'path': created_files['test_doc.xlsx'], 'type': 'excel', 'name': 'test_doc.xlsx'},
            {'path': created_files['test_doc.xlsx'].replace('/', '\\'), 'type': 'excel', 'name': 'test_doc.xlsx'},  # Different separators
            {'path': os.path.relpath(created_files['test_doc.xlsx']), 'type': 'excel', 'name': 'test_doc.xlsx'},  # Relative path
            {'path': created_files['subdir/another_doc.docx'], 'type': 'word', 'name': 'another_doc.docx'},
        ]
        
        # Test deduplication
        unique_artifacts = self.orchestrator._deduplicate_artifacts_robust(artifacts)
        
        print(f"Input artifacts: {len(artifacts)}")
        print(f"Unique artifacts after deduplication: {len(unique_artifacts)}")
        
        # Should have only 2 unique files despite 4 input artifacts
        assert len(unique_artifacts) == 2, f"Expected 2 unique artifacts, got {len(unique_artifacts)}"
        print("✓ Path normalization test passed")
        
    def test_tool_execution_validation(self):
        """Test tool execution status validation"""
        print("\n=== Testing Tool Execution Validation ===")
        
        test_cases = [
            ("File created successfully: test.xlsx", True),
            ("Excel file generated successfully", True),
            ("Error: Failed to create file", False),
            ("Exception occurred while processing", False),
            ("Permission denied when writing file", False),
            ("Document saved to temp/output.docx", True),
            ("Could not save file to disk", False),
            ("Generated chart.png successfully", True),
            ("Traceback: FileNotFoundError", False),
        ]
        
        for result_text, expected in test_cases:
            actual = self.orchestrator._validate_tool_execution_status(result_text)
            print(f"  '{result_text[:30]}...' -> {actual} (expected: {expected})")
            assert actual == expected, f"Failed for: {result_text}"
            
        print("✓ Tool execution validation test passed")
        
    def test_artifact_filtering_for_failed_tools(self):
        """Test artifact filtering when tools fail"""
        print("\n=== Testing Artifact Filtering for Failed Tools ===")
        
        # Create test files
        test_files = {
            'success_file.xlsx': 'Valid content',
            'failed_file.docx': 'Partial content from failed tool',
        }
        
        created_files = self.create_test_files(test_files)
        
        # Create artifacts
        artifacts = [
            {'path': created_files['success_file.xlsx'], 'type': 'excel', 'name': 'success_file.xlsx'},
            {'path': created_files['failed_file.docx'], 'type': 'word', 'name': 'failed_file.docx'},
        ]
        
        # Test with successful result mentioning the first file
        success_result = "Excel file success_file.xlsx created successfully. Processing complete."
        filtered = self.orchestrator._filter_artifacts_for_failed_tools(artifacts, success_result)
        
        print(f"Artifacts with successful result: {len(filtered)} (should be 1)")
        assert len(filtered) == 1, f"Expected 1 artifact with success context, got {len(filtered)}"
        assert filtered[0]['name'] == 'success_file.xlsx'
        
        # Test with failed result
        failed_result = "Error occurred during processing. Some files may be incomplete."
        filtered = self.orchestrator._filter_artifacts_for_failed_tools(artifacts, failed_result)
        
        print(f"Artifacts with failed result: {len(filtered)} (should be 0)")
        assert len(filtered) == 0, f"Expected 0 artifacts with failed result, got {len(filtered)}"
        
        print("✓ Artifact filtering test passed")
        
    def test_database_duplicate_prevention(self):
        """Test database-level duplicate prevention"""
        print("\n=== Testing Database Duplicate Prevention ===")
        
        # Create test message
        message = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Test message for artifact deduplication'
        )
        
        # Create test file
        test_files = {'test_artifact.xlsx': 'Test content'}
        created_files = self.create_test_files(test_files)
        
        # Create artifact data
        artifacts = [
            {'path': created_files['test_artifact.xlsx'], 'type': 'excel', 'name': 'test_artifact.xlsx'},
            {'path': created_files['test_artifact.xlsx'], 'type': 'file', 'name': 'test_artifact.xlsx'},  # Duplicate
        ]
        
        # Test artifact creation (should prevent duplicates)
        self.orchestrator._create_artifact_records(artifacts, message)
        
        # Check database
        db_artifacts = Artifact.objects.filter(message=message)
        print(f"Artifacts in database: {db_artifacts.count()} (should be 1)")
        
        assert db_artifacts.count() == 1, f"Expected 1 database artifact, got {db_artifacts.count()}"
        
        print("✓ Database duplicate prevention test passed")
        
    def test_end_to_end_deduplication(self):
        """Test complete end-to-end deduplication workflow"""
        print("\n=== Testing End-to-End Deduplication ===")
        
        # Create test files in temp directory structure similar to real usage
        temp_subdir = os.path.join('temp', 'test_artifacts')
        os.makedirs(temp_subdir, exist_ok=True)
        
        test_files = {
            os.path.join(temp_subdir, 'document.xlsx'): 'Excel content',
            os.path.join(temp_subdir, 'report.docx'): 'Word content',
        }
        
        created_files = self.create_test_files(test_files)
        
        # Simulate before/after filesystem state
        files_before = {}
        files_after = {
            path: os.path.getmtime(path) for path in created_files.values()
        }
        
        # Mock agent result that would cause multiple detections
        mock_result = """
        Excel file created successfully: temp/test_artifacts/document.xlsx
        Word document generated: temp/test_artifacts/report.docx
        Files saved to temp/test_artifacts/
        Processing completed successfully.
        """
        
        # Test enhanced artifact extraction
        artifacts = self.orchestrator._extract_artifacts_enhanced(
            mock_result, files_before, files_after
        )
        
        print(f"Extracted artifacts: {len(artifacts)}")
        for i, artifact in enumerate(artifacts):
            print(f"  {i+1}. {artifact.get('name', 'unknown')} ({artifact.get('detection_source', 'unknown')})")
        
        # Should have exactly 2 unique artifacts despite multiple detection methods
        assert len(artifacts) == 2, f"Expected 2 unique artifacts, got {len(artifacts)}"
        
        artifact_names = {a.get('name') for a in artifacts}
        expected_names = {'document.xlsx', 'report.docx'}
        assert artifact_names == expected_names, f"Expected {expected_names}, got {artifact_names}"
        
        print("✓ End-to-end deduplication test passed")
        
    def run_all_tests(self):
        """Run all deduplication tests"""
        try:
            self.setup()
            
            print("🔍 Running Artifact Deduplication Tests")
            print("=" * 50)
            
            self.test_path_normalization()
            self.test_tool_execution_validation()
            self.test_artifact_filtering_for_failed_tools()
            self.test_database_duplicate_prevention()
            self.test_end_to_end_deduplication()
            
            print("\n" + "=" * 50)
            print("✅ All tests passed! Document preview duplication should be resolved.")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            self.cleanup()

def main():
    """Main test execution"""
    print("Starting Artifact Deduplication Test Suite")
    print("This tests the fixes for document preview duplication issues")
    print()
    
    test_suite = ArtifactDeduplicationTests()
    success = test_suite.run_all_tests()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("The document preview duplication issue should now be fixed.")
    else:
        print("\n💥 Some tests failed. Please review the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()