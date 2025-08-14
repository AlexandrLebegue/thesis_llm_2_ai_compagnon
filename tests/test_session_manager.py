import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.sessions.models import Session
from django.conf import settings
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from tests.conftest import BaseTestCase, TestFileGenerator

# Import modules to test
from apps.documents.models import DocumentSession, Document, DocumentContext
from apps.documents.session_manager import SessionManager
from apps.documents.storage import SessionFileStorage


class TestSessionManagerInitialization(BaseTestCase):
    """Test SessionManager initialization and basic properties"""
    
    def test_session_manager_initialization(self):
        """Test SessionManager initialization"""
        manager = SessionManager('test_session_key')
        
        self.assertEqual(manager.session_key, 'test_session_key')
        self.assertIsNone(manager._doc_session)
        self.assertIsNone(manager._storage)
    
    def test_doc_session_property_creates_session(self):
        """Test that doc_session property creates session if needed"""
        manager = SessionManager('new_session_key')
        
        # Access doc_session property
        doc_session = manager.doc_session
        
        # Should create Session and DocumentSession
        self.assertIsNotNone(doc_session)
        self.assertIsInstance(doc_session, DocumentSession)
        self.assertEqual(doc_session.session.session_key, 'new_session_key')
    
    def test_doc_session_property_reuses_existing(self):
        """Test that doc_session property reuses existing session"""
        manager = SessionManager(self.session.session_key)
        
        # Access doc_session property multiple times
        doc_session1 = manager.doc_session
        doc_session2 = manager.doc_session
        
        # Should return the same instance
        self.assertEqual(doc_session1, doc_session2)
        self.assertEqual(doc_session1, self.doc_session)
    
    def test_storage_property_creates_storage(self):
        """Test that storage property creates SessionFileStorage"""
        manager = SessionManager('storage_test_key')
        
        storage = manager.storage
        
        self.assertIsNotNone(storage)
        self.assertIsInstance(storage, SessionFileStorage)
        self.assertEqual(storage.session_id, 'storage_test_key')
    
    def test_storage_property_reuses_existing(self):
        """Test that storage property reuses existing storage"""
        manager = SessionManager('storage_test_key')
        
        storage1 = manager.storage
        storage2 = manager.storage
        
        # Should return the same instance
        self.assertEqual(storage1, storage2)


class TestSessionManagerDocumentLimits(BaseTestCase):
    """Test document limit enforcement"""
    
    def setUp(self):
        super().setUp()
        self.manager = SessionManager(self.session.session_key)
        self.file_generator = TestFileGenerator()
    
    def test_can_add_document_within_limits(self):
        """Test can_add_document returns True when within limits"""
        can_add, message = self.manager.can_add_document(1024)
        
        self.assertTrue(can_add)
        self.assertEqual(message, "")
    
    def test_can_add_document_exceeds_count_limit(self):
        """Test can_add_document when document count limit exceeded"""
        # Create maximum number of documents
        for i in range(settings.MAX_DOCUMENTS_PER_SESSION):
            self.create_test_document(f"doc{i}.pdf", "pdf", "ready")
        
        can_add, message = self.manager.can_add_document(1024)
        
        self.assertFalse(can_add)
        self.assertIn('Maximum', message)
        self.assertIn(str(settings.MAX_DOCUMENTS_PER_SESSION), message)
    
    def test_can_add_document_exceeds_size_limit(self):
        """Test can_add_document when session size limit exceeded"""
        # Set current session size near limit
        self.doc_session.total_size = 90 * 1024 * 1024  # 90MB
        self.doc_session.save()
        
        # Try to add 20MB file (would exceed 100MB limit)
        can_add, message = self.manager.can_add_document(20 * 1024 * 1024)
        
        self.assertFalse(can_add)
        self.assertIn('storage limit exceeded', message)
        self.assertIn('100MB max', message)
    
    def test_can_add_document_exceeds_file_size_limit(self):
        """Test can_add_document when individual file is too large"""
        large_file_size = settings.MAX_FILE_SIZE + 1
        
        can_add, message = self.manager.can_add_document(large_file_size)
        
        self.assertFalse(can_add)
        self.assertIn('File too large', message)
    
    def test_can_add_document_exact_limits(self):
        """Test can_add_document at exact limit boundaries"""
        # Test exact count limit
        for i in range(settings.MAX_DOCUMENTS_PER_SESSION - 1):
            self.create_test_document(f"doc{i}.pdf", "pdf", "ready")
        
        can_add, message = self.manager.can_add_document(1024)
        self.assertTrue(can_add)  # Should still allow one more
        
        # Add one more to reach exact limit
        self.create_test_document("last_doc.pdf", "pdf", "ready")
        
        can_add, message = self.manager.can_add_document(1024)
        self.assertFalse(can_add)  # Should now be at limit
    
    def test_can_add_document_exact_size_limit(self):
        """Test can_add_document at exact size limit"""
        # Set session size to exact limit minus small amount
        self.doc_session.total_size = 100 * 1024 * 1024 - 1024  # 100MB - 1KB
        self.doc_session.save()
        
        # Should allow 1KB file
        can_add, message = self.manager.can_add_document(1024)
        self.assertTrue(can_add)
        
        # Should not allow 2KB file
        can_add, message = self.manager.can_add_document(2048)
        self.assertFalse(can_add)


class TestSessionManagerDocumentOperations(BaseTestCase):
    """Test document addition and removal operations"""
    
    def setUp(self):
        super().setUp()
        self.manager = SessionManager(self.session.session_key)
        self.file_generator = TestFileGenerator()
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Mock storage to use test directory
        with patch.object(self.manager, '_storage', None):
            self.manager._storage = SessionFileStorage(
                session_id=self.session.session_key,
                base_path=self.test_dir
            )
    
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_add_document_success(self):
        """Test successful document addition"""
        test_file = self.file_generator.create_pdf_file("add_test.pdf")
        
        document = self.manager.add_document(test_file, "pdf")
        
        self.assertIsNotNone(document)
        self.assertEqual(document.original_name, "add_test.pdf")
        self.assertEqual(document.document_type, "pdf")
        self.assertEqual(document.session, self.doc_session)
        self.assertIsNotNone(document.file_path)
        
        # Check that session totals were updated
        self.doc_session.refresh_from_db()
        self.assertEqual(self.doc_session.document_count, 1)
        self.assertEqual(self.doc_session.total_size, test_file.size)
    
    def test_add_document_validates_limits(self):
        """Test that add_document validates limits"""
        # Create maximum number of documents
        for i in range(settings.MAX_DOCUMENTS_PER_SESSION):
            self.create_test_document(f"limit{i}.pdf", "pdf", "ready")
        
        test_file = self.file_generator.create_pdf_file("overflow.pdf")
        
        with self.assertRaises(ValueError) as context:
            self.manager.add_document(test_file, "pdf")
        
        self.assertIn('Maximum', str(context.exception))
    
    def test_add_document_storage_failure_cleanup(self):
        """Test that document is cleaned up if storage fails"""
        test_file = self.file_generator.create_pdf_file("fail_test.pdf")
        
        with patch.object(self.manager.storage, 'save') as mock_save:
            mock_save.side_effect = Exception("Storage failed")
            
            with self.assertRaises(Exception):
                self.manager.add_document(test_file, "pdf")
        
        # Document should not exist in database
        self.assertFalse(
            Document.objects.filter(original_name="fail_test.pdf").exists()
        )
    
    def test_remove_document_success(self):
        """Test successful document removal"""
        # Create test document
        document = self.create_test_document("remove_test.pdf", "pdf", "ready")
        document_id = str(document.id)
        
        # Mock storage delete
        with patch.object(self.manager.storage, 'delete') as mock_delete:
            result = self.manager.remove_document(document_id)
        
        self.assertTrue(result)
        mock_delete.assert_called_once_with(document.file_path)
        
        # Document should be deleted from database
        self.assertFalse(Document.objects.filter(id=document_id).exists())
        
        # Session totals should be updated
        self.doc_session.refresh_from_db()
        self.assertEqual(self.doc_session.document_count, 0)
        self.assertEqual(self.doc_session.total_size, 0)
    
    def test_remove_document_not_found(self):
        """Test removing non-existent document"""
        fake_id = '12345678-1234-5678-9012-123456789012'
        
        result = self.manager.remove_document(fake_id)
        
        self.assertFalse(result)
    
    def test_remove_document_storage_failure_continues(self):
        """Test that document removal continues even if storage delete fails"""
        document = self.create_test_document("storage_fail.pdf", "pdf", "ready")
        document_id = str(document.id)
        
        with patch.object(self.manager.storage, 'delete') as mock_delete:
            mock_delete.side_effect = Exception("Storage delete failed")
            
            result = self.manager.remove_document(document_id)
        
        # Should still succeed
        self.assertTrue(result)
        
        # Document should still be deleted from database
        self.assertFalse(Document.objects.filter(id=document_id).exists())
    
    def test_update_session_totals(self):
        """Test updating session totals"""
        # Create test documents
        doc1 = self.create_test_document("total1.pdf", "pdf", "ready")
        doc2 = self.create_test_document("total2.xlsx", "xlsx", "ready")
        
        # Manually reset totals
        self.doc_session.document_count = 0
        self.doc_session.total_size = 0
        self.doc_session.save()
        
        # Update totals
        self.manager.update_session_totals()
        
        # Check that totals are correct
        self.doc_session.refresh_from_db()
        self.assertEqual(self.doc_session.document_count, 2)
        self.assertEqual(self.doc_session.total_size, doc1.file_size + doc2.file_size)


class TestSessionManagerInformation(BaseTestCase):
    """Test session information and statistics"""
    
    def setUp(self):
        super().setUp()
        self.manager = SessionManager(self.session.session_key)
    
    def test_get_session_info_basic(self):
        """Test basic session info retrieval"""
        info = self.manager.get_session_info()
        
        self.assertEqual(info['session_key'], self.session.session_key)
        self.assertEqual(info['document_count'], 0)
        self.assertEqual(info['total_size'], 0)
        self.assertEqual(info['max_documents'], settings.MAX_DOCUMENTS_PER_SESSION)
        self.assertEqual(info['remaining_slots'], settings.MAX_DOCUMENTS_PER_SESSION)
        self.assertIn('status_breakdown', info)
        self.assertIn('type_breakdown', info)
        self.assertIn('created_at', info)
        self.assertIn('storage_path', info)
    
    def test_get_session_info_with_documents(self):
        """Test session info with documents"""
        # Create test documents with different statuses and types
        self.create_test_document("ready1.pdf", "pdf", "ready")
        self.create_test_document("ready2.pdf", "pdf", "ready")
        self.create_test_document("processing.xlsx", "xlsx", "processing")
        self.create_test_document("pending.docx", "docx", "pending")
        self.create_test_document("error.pdf", "pdf", "error")
        
        info = self.manager.get_session_info()
        
        self.assertEqual(info['document_count'], 5)
        self.assertEqual(info['remaining_slots'], settings.MAX_DOCUMENTS_PER_SESSION - 5)
        
        # Check status breakdown
        status_breakdown = info['status_breakdown']
        self.assertEqual(status_breakdown['ready'], 2)
        self.assertEqual(status_breakdown['processing'], 1)
        self.assertEqual(status_breakdown['pending'], 1)
        self.assertEqual(status_breakdown['error'], 1)
        
        # Check type breakdown
        type_breakdown = info['type_breakdown']
        self.assertEqual(type_breakdown['pdf'], 3)
        self.assertEqual(type_breakdown['xlsx'], 1)
        self.assertEqual(type_breakdown['docx'], 1)
    
    def test_get_document_list(self):
        """Test getting document list with details"""
        # Create test documents
        doc1 = self.create_test_document("list1.pdf", "pdf", "ready")
        doc2 = self.create_test_document("list2.xlsx", "xlsx", "processing")
        
        document_list = self.manager.get_document_list()
        
        self.assertEqual(len(document_list), 2)
        
        # Check document details (should be ordered by upload date, most recent first)
        doc_info = document_list[0]  # Most recent (doc2)
        self.assertEqual(doc_info['name'], 'list2.xlsx')
        self.assertEqual(doc_info['type'], 'xlsx')
        self.assertEqual(doc_info['status'], 'processing')
        self.assertEqual(doc_info['size'], 1024)
        self.assertEqual(doc_info['size_mb'], round(1024 / (1024 * 1024), 2))
        self.assertIn('uploaded_at', doc_info)
        self.assertTrue(doc_info['is_ready'] is False)
        self.assertFalse(doc_info['has_error'])
        
        # Check first document
        doc_info = document_list[1]  # Older (doc1)
        self.assertEqual(doc_info['name'], 'list1.pdf')
        self.assertTrue(doc_info['is_ready'])


class TestSessionManagerCleanup(BaseTestCase):
    """Test session cleanup functionality"""
    
    def setUp(self):
        super().setUp()
        self.manager = SessionManager(self.session.session_key)
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Mock storage to use test directory
        with patch('apps.documents.session_manager.settings.TEMP_FILE_ROOT', self.test_dir):
            self.manager._storage = SessionFileStorage(
                session_id=self.session.session_key,
                base_path=self.test_dir / self.session.session_key
            )
    
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_cleanup_session_without_force(self):
        """Test session cleanup without force flag"""
        # Create test documents and files
        doc1 = self.create_test_document("cleanup1.pdf", "pdf", "ready")
        doc2 = self.create_test_document("cleanup2.xlsx", "xlsx", "ready")
        
        # Create test files in storage
        storage_path = self.test_dir / self.session.session_key
        storage_path.mkdir(parents=True, exist_ok=True)
        (storage_path / "cleanup1.pdf").write_text("test content 1")
        (storage_path / "cleanup2.xlsx").write_text("test content 2")
        
        # Cleanup session
        self.manager.cleanup_session(force=False)
        
        # Files should be deleted
        self.assertFalse((storage_path / "cleanup1.pdf").exists())
        self.assertFalse((storage_path / "cleanup2.xlsx").exists())
        
        # Documents should be deleted
        self.assertFalse(Document.objects.filter(id=doc1.id).exists())
        self.assertFalse(Document.objects.filter(id=doc2.id).exists())
        
        # DocumentSession should still exist but with reset counts
        self.doc_session.refresh_from_db()
        self.assertEqual(self.doc_session.document_count, 0)
        self.assertEqual(self.doc_session.total_size, 0)
    
    def test_cleanup_session_with_force(self):
        """Test session cleanup with force flag"""
        # Create test documents
        self.create_test_document("force_cleanup.pdf", "pdf", "ready")
        
        doc_session_id = self.doc_session.id
        
        # Cleanup with force
        self.manager.cleanup_session(force=True)
        
        # DocumentSession should be deleted
        self.assertFalse(DocumentSession.objects.filter(id=doc_session_id).exists())
    
    def test_cleanup_session_handles_file_errors(self):
        """Test that cleanup handles file deletion errors gracefully"""
        # Create test document
        doc = self.create_test_document("error_cleanup.pdf", "pdf", "ready")
        
        # Create test file with restricted permissions
        storage_path = self.test_dir / self.session.session_key
        storage_path.mkdir(parents=True, exist_ok=True)
        test_file = storage_path / "error_cleanup.pdf"
        test_file.write_text("test content")
        
        # Mock file deletion to raise error
        with patch('pathlib.Path.unlink') as mock_unlink:
            mock_unlink.side_effect = PermissionError("Cannot delete file")
            
            # Should not raise exception
            self.manager.cleanup_session(force=False)
        
        # Document should still be deleted from database
        self.assertFalse(Document.objects.filter(id=doc.id).exists())


class TestSessionManagerClassMethods(BaseTestCase):
    """Test SessionManager class methods for bulk operations"""
    
    def setUp(self):
        super().setUp()
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions"""
        # Create old sessions
        old_time = timezone.now() - timedelta(hours=48)
        
        old_session1 = Session.objects.create(
            session_key='old_session_1',
            session_data='{}'
        )
        old_doc_session1 = DocumentSession.objects.create(
            session=old_session1,
            created_at=old_time
        )
        
        old_session2 = Session.objects.create(
            session_key='old_session_2',
            session_data='{}'
        )
        old_doc_session2 = DocumentSession.objects.create(
            session=old_session2,
            created_at=old_time
        )
        
        # Create recent session (should not be cleaned)
        recent_session = Session.objects.create(
            session_key='recent_session',
            session_data='{}'
        )
        recent_doc_session = DocumentSession.objects.create(
            session=recent_session
        )
        
        # Run cleanup for sessions older than 24 hours
        with patch('apps.documents.session_manager.SessionManager.cleanup_session') as mock_cleanup:
            cleaned_count = SessionManager.cleanup_expired_sessions(hours=24)
        
        self.assertEqual(cleaned_count, 2)
        self.assertEqual(mock_cleanup.call_count, 2)
        
        # Recent session should still exist
        self.assertTrue(DocumentSession.objects.filter(id=recent_doc_session.id).exists())
    
    def test_cleanup_expired_sessions_handles_errors(self):
        """Test that expired session cleanup handles individual errors"""
        # Create old session
        old_time = timezone.now() - timedelta(hours=48)
        old_session = Session.objects.create(
            session_key='error_session',
            session_data='{}'
        )
        old_doc_session = DocumentSession.objects.create(
            session=old_session,
            created_at=old_time
        )
        
        # Mock cleanup to raise error
        with patch('apps.documents.session_manager.SessionManager.cleanup_session') as mock_cleanup:
            mock_cleanup.side_effect = Exception("Cleanup failed")
            
            cleaned_count = SessionManager.cleanup_expired_sessions(hours=24)
        
        # Should return 0 due to error, but not crash
        self.assertEqual(cleaned_count, 0)
    
    @patch('apps.documents.session_manager.settings.TEMP_FILE_ROOT')
    def test_cleanup_orphaned_files(self, mock_temp_root):
        """Test cleanup of orphaned files"""
        mock_temp_root.return_value = self.test_dir
        mock_temp_root.exists.return_value = True
        
        # Create directory structure with orphaned files
        session_dir = self.test_dir / 'orphaned_session'
        session_dir.mkdir(parents=True)
        orphaned_file = session_dir / 'orphaned.pdf'
        orphaned_file.write_text("orphaned content")
        
        # Create valid session directory
        valid_session = Session.objects.create(
            session_key='valid_session',
            session_data='{}'
        )
        valid_doc_session = DocumentSession.objects.create(session=valid_session)
        
        valid_session_dir = self.test_dir / 'valid_session'
        valid_session_dir.mkdir(parents=True)
        
        # Create file with corresponding database record
        valid_file = valid_session_dir / 'valid.pdf'
        valid_file.write_text("valid content")
        Document.objects.create(
            session=valid_doc_session,
            original_name='valid.pdf',
            file_path='valid_session/valid.pdf',
            document_type='pdf',
            file_size=1024,
            status='ready'
        )
        
        # Create orphaned file in valid session
        orphaned_in_valid = valid_session_dir / 'orphaned_in_valid.pdf'
        orphaned_in_valid.write_text("orphaned in valid session")
        
        with patch('apps.documents.session_manager.settings.TEMP_FILE_ROOT', self.test_dir):
            cleaned_count = SessionManager.cleanup_orphaned_files()
        
        # Should clean up orphaned files
        self.assertGreater(cleaned_count, 0)
        
        # Orphaned session directory should be cleaned
        self.assertFalse(orphaned_file.exists())
        
        # Valid file should remain
        self.assertTrue(valid_file.exists())
        
        # Orphaned file in valid session should be cleaned
        self.assertFalse(orphaned_in_valid.exists())
    
    @patch('apps.documents.session_manager.settings.TEMP_FILE_ROOT')
    def test_cleanup_orphaned_files_no_temp_root(self, mock_temp_root):
        """Test cleanup when temp root doesn't exist"""
        mock_temp_root.return_value = Path('/nonexistent')
        mock_temp_root.exists.return_value = False
        
        with patch('apps.documents.session_manager.settings.TEMP_FILE_ROOT', Path('/nonexistent')):
            cleaned_count = SessionManager.cleanup_orphaned_files()
        
        self.assertEqual(cleaned_count, 0)
    
    def test_cleanup_orphaned_files_handles_errors(self):
        """Test that orphaned file cleanup handles errors gracefully"""
        # Create test directory with file
        session_dir = self.test_dir / 'error_session'
        session_dir.mkdir(parents=True)
        test_file = session_dir / 'error.pdf'
        test_file.write_text("test content")
        
        # Mock file deletion to raise error
        with patch('pathlib.Path.unlink') as mock_unlink:
            mock_unlink.side_effect = PermissionError("Cannot delete")
            
            with patch('apps.documents.session_manager.settings.TEMP_FILE_ROOT', self.test_dir):
                cleaned_count = SessionManager.cleanup_orphaned_files()
        
        # Should handle error gracefully
        self.assertEqual(cleaned_count, 0)


class TestSessionManagerEdgeCases(BaseTestCase):
    """Test edge cases and error conditions"""
    
    def setUp(self):
        super().setUp()
        self.manager = SessionManager(self.session.session_key)
    
    def test_session_manager_with_invalid_session_key(self):
        """Test SessionManager with non-existent session key"""
        manager = SessionManager('nonexistent_key')
        
        # Should create new session when accessed
        doc_session = manager.doc_session
        
        self.assertIsNotNone(doc_session)
        self.assertEqual(doc_session.session.session_key, 'nonexistent_key')
    
    def test_can_add_document_zero_size(self):
        """Test can_add_document with zero-size file"""
        can_add, message = self.manager.can_add_document(0)
        
        self.assertTrue(can_add)
        self.assertEqual(message, "")
    
    def test_can_add_document_negative_size(self):
        """Test can_add_document with negative size"""
        can_add, message = self.manager.can_add_document(-100)
        
        # Should still pass validation (size validation happens elsewhere)
        self.assertTrue(can_add)
    
    def test_update_session_totals_no_documents(self):
        """Test updating session totals with no documents"""
        self.manager.update_session_totals()
        
        self.doc_session.refresh_from_db()
        self.assertEqual(self.doc_session.document_count, 0)
        self.assertEqual(self.doc_session.total_size, 0)
    
    def test_get_document_list_empty(self):
        """Test getting document list when no documents exist"""
        document_list = self.manager.get_document_list()
        
        self.assertEqual(len(document_list), 0)
        self.assertIsInstance(document_list, list)
    
    def test_cleanup_session_no_files(self):
        """Test session cleanup when no files exist"""
        # Should not raise exception
        self.manager.cleanup_session(force=False)
        
        # Session should still exist
        self.assertTrue(DocumentSession.objects.filter(id=self.doc_session.id).exists())
    
    def test_session_manager_concurrent_access(self):
        """Test SessionManager with concurrent access simulation"""
        manager1 = SessionManager(self.session.session_key)
        manager2 = SessionManager(self.session.session_key)
        
        # Both should get the same DocumentSession
        doc_session1 = manager1.doc_session
        doc_session2 = manager2.doc_session
        
        self.assertEqual(doc_session1.id, doc_session2.id)


if __name__ == '__main__':
    import unittest
    unittest.main()