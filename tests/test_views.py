import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.sessions.models import Session
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from tests.conftest import BaseTestCase, TestFileGenerator

# Import models and views
from apps.documents.models import DocumentSession, Document, DocumentContext
from apps.chat.models import Conversation, Message, Artifact
from apps.chat.views import ChatView
from apps.documents.views import DocumentView


class TestChatViewIndex(BaseTestCase):
    """Test ChatView index endpoint"""
    
    def test_index_get_success(self):
        """Test successful GET request to chat index"""
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'documents')
        self.assertContains(response, 'messages')
        self.assertContains(response, 'max_documents')
    
    def test_index_creates_session_and_conversation(self):
        """Test that index creates session and conversation if they don't exist"""
        # Clear any existing session
        self.client.session.flush()
        
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        
        # Check that session was created
        session_key = self.client.session.session_key
        self.assertIsNotNone(session_key)
        
        # Check that DocumentSession was created
        doc_session = DocumentSession.objects.get(session__session_key=session_key)
        self.assertIsNotNone(doc_session)
        
        # Check that Conversation was created
        conversation = Conversation.objects.get(session=doc_session)
        self.assertIsNotNone(conversation)
    
    def test_index_with_existing_documents_and_messages(self):
        """Test index with existing documents and messages"""
        # Create test documents
        doc1 = self.create_test_document("test1.pdf", "pdf", "ready")
        doc2 = self.create_test_document("test2.xlsx", "xlsx", "ready")
        
        # Create test messages
        msg1 = self.create_test_message("user", "Hello")
        msg2 = self.create_test_message("assistant", "Hi there!")
        
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test1.pdf")
        self.assertContains(response, "test2.xlsx")
        self.assertEqual(response.context['current_document_count'], 2)


class TestChatViewSendMessage(BaseTestCase):
    """Test ChatView send_message endpoint"""
    
    def setUp(self):
        super().setUp()
        self.send_message_url = '/send/'
        self.file_generator = TestFileGenerator()
    
    @patch('apps.chat.views.CELERY_AVAILABLE', False)
    @patch('apps.agents.orchestrator.ChatbotOrchestrator')
    def test_send_message_text_only_success(self, mock_orchestrator_class):
        """Test successful message sending without files"""
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_request.return_value = {
            'result': 'Test response from agent',
            'artifacts': []
        }
        mock_orchestrator_class.return_value = mock_orchestrator
        
        response = self.client.post(self.send_message_url, {
            'message': 'Test message content'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check that user message was created
        user_messages = Message.objects.filter(role='user', content='Test message content')
        self.assertEqual(user_messages.count(), 1)
        
        # Check that assistant message was created
        assistant_messages = Message.objects.filter(role='assistant')
        self.assertEqual(assistant_messages.count(), 1)
        
        # Check orchestrator was called
        mock_orchestrator.process_request.assert_called_once()
    
    @patch('apps.chat.views.CELERY_AVAILABLE', False)
    def test_send_message_with_file_upload(self):
        """Test message sending with file upload"""
        test_file = self.file_generator.create_pdf_file("test.pdf")
        
        response = self.client.post(self.send_message_url, {
            'message': 'Process this file',
            'files': [test_file]
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check that document was created
        documents = Document.objects.filter(original_name='test.pdf')
        self.assertEqual(documents.count(), 1)
        
        document = documents.first()
        self.assertEqual(document.document_type, 'pdf')
        self.assertEqual(document.status, 'ready')  # No Celery, so marked as ready
    
    def test_send_message_exceeds_document_limit(self):
        """Test message sending when document limit is exceeded"""
        # Create max number of documents
        for i in range(settings.MAX_DOCUMENTS_PER_SESSION):
            self.create_test_document(f"doc{i}.pdf", "pdf", "ready")
        
        test_file = self.file_generator.create_pdf_file("overflow.pdf")
        
        response = self.client.post(self.send_message_url, {
            'message': 'This should fail',
            'files': [test_file]
        }, follow=True)
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('Maximum', response_data['error'])
    
    @patch('apps.chat.views.CELERY_AVAILABLE', True)
    @patch('apps.chat.views.run_agent_task_async')
    def test_send_message_async_processing(self, mock_async_task):
        """Test message sending with async processing"""
        # Mock async task
        mock_task = MagicMock()
        mock_task.id = 'task_123'
        mock_async_task.delay.return_value = mock_task
        
        # Create multiple documents to trigger async processing
        for i in range(5):
            self.create_test_document(f"doc{i}.pdf", "pdf", "ready")
        
        response = self.client.post(self.send_message_url, {
            'message': 'analyze all documents'  # Should trigger async
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check that async task was queued
        mock_async_task.delay.assert_called_once()
        
        # Check that pending message was created
        pending_messages = Message.objects.filter(
            role='assistant',
            task_id='task_123',
            task_status='PENDING'
        )
        self.assertEqual(pending_messages.count(), 1)
    
    def test_send_message_no_session(self):
        """Test message sending without active session"""
        # Create client without session
        client = Client()
        
        response = client.post(self.send_message_url, {
            'message': 'Test message'
        })
        
        # Should handle gracefully and create session
        self.assertEqual(response.status_code, 200)
    
    def test_send_message_invalid_method(self):
        """Test send_message with invalid HTTP method"""
        response = self.client.get(self.send_message_url)
        
        self.assertEqual(response.status_code, 405)  # Method not allowed


class TestChatViewTaskStatus(BaseTestCase):
    """Test ChatView check_task_status endpoint"""
    
    def setUp(self):
        super().setUp()
        self.task_status_url = '/task_status/'
    
    @patch('apps.chat.views.CELERY_AVAILABLE', False)
    def test_check_task_status_celery_unavailable(self):
        """Test task status check when Celery is unavailable"""
        response = self.client.get(f'{self.task_status_url}test_task_id/')
        
        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertIn('not available', response_data['error'])
    
    @patch('apps.chat.views.CELERY_AVAILABLE', True)
    @patch('apps.chat.views.AsyncResult')
    def test_check_task_status_success(self, mock_async_result_class):
        """Test successful task status check"""
        # Create test message with task
        message = self.create_test_message("assistant", "Processing...", task_id="task_123")
        
        # Mock AsyncResult
        mock_result = MagicMock()
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.get.return_value = {
            'result': 'Task completed successfully',
            'artifacts': []
        }
        mock_async_result_class.return_value = mock_result
        
        response = self.client.get(f'{self.task_status_url}task_123/')
        
        self.assertEqual(response.status_code, 200)
        
        # Check that message was updated
        message.refresh_from_db()
        self.assertEqual(message.content, 'Task completed successfully')
        self.assertEqual(message.task_status, 'SUCCESS')
    
    @patch('apps.chat.views.CELERY_AVAILABLE', True)
    @patch('apps.chat.views.AsyncResult')
    def test_check_task_status_failure(self, mock_async_result_class):
        """Test task status check for failed task"""
        # Create test message with task
        message = self.create_test_message("assistant", "Processing...", task_id="task_456")
        
        # Mock AsyncResult for failure
        mock_result = MagicMock()
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.info = "Task failed with error"
        mock_async_result_class.return_value = mock_result
        
        response = self.client.get(f'{self.task_status_url}task_456/')
        
        self.assertEqual(response.status_code, 200)
        
        # Check that message was updated with error
        message.refresh_from_db()
        self.assertIn('Error:', message.content)
        self.assertEqual(message.task_status, 'FAILURE')
    
    @patch('apps.chat.views.CELERY_AVAILABLE', True)
    @patch('apps.chat.views.AsyncResult')
    def test_check_task_status_pending(self, mock_async_result_class):
        """Test task status check for still-running task"""
        # Create test message with task
        message = self.create_test_message("assistant", "Processing...", task_id="task_789")
        
        # Mock AsyncResult for pending task
        mock_result = MagicMock()
        mock_result.ready.return_value = False
        mock_async_result_class.return_value = mock_result
        
        response = self.client.get(f'{self.task_status_url}task_789/')
        
        self.assertEqual(response.status_code, 200)
        
        # Message should remain unchanged
        message.refresh_from_db()
        self.assertEqual(message.content, "Processing...")


class TestChatViewDownloadArtifact(BaseTestCase):
    """Test ChatView download_artifact endpoint"""
    
    def setUp(self):
        super().setUp()
        self.download_url = '/download/'
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('apps.chat.downloads.ArtifactDownloader')
    def test_download_artifact_success(self, mock_downloader_class):
        """Test successful artifact download"""
        # Create test message and artifact
        message = self.create_test_message("assistant", "Here's your file")
        artifact = Artifact.objects.create(
            message=message,
            file_path=str(self.test_dir / "test.pdf"),
            file_name="test.pdf",
            file_type="application/pdf",
            file_size=1024,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Mock downloader
        mock_downloader = MagicMock()
        mock_response = HttpResponse(b'test content', content_type='application/pdf')
        mock_downloader.download_artifact.return_value = mock_response
        mock_downloader_class.return_value = mock_downloader
        
        response = self.client.get(f'{self.download_url}{artifact.id}/')
        
        self.assertEqual(response.status_code, 200)
        mock_downloader.download_artifact.assert_called_once_with(artifact)
    
    def test_download_artifact_not_found(self):
        """Test download of non-existent artifact"""
        fake_id = '12345678-1234-5678-9012-123456789012'
        
        response = self.client.get(f'{self.download_url}{fake_id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_download_artifact_wrong_session(self):
        """Test download artifact from different session"""
        # Create artifact in different session
        other_session = Session.objects.create(
            session_key='other_session',
            session_data='{}'
        )
        other_doc_session = DocumentSession.objects.create(session=other_session)
        other_conversation = Conversation.objects.create(session=other_doc_session)
        other_message = Message.objects.create(
            conversation=other_conversation,
            role='assistant',
            content='Other user file'
        )
        
        artifact = Artifact.objects.create(
            message=other_message,
            file_path=str(self.test_dir / "other.pdf"),
            file_name="other.pdf",
            file_type="application/pdf",
            file_size=1024,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        response = self.client.get(f'{self.download_url}{artifact.id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_download_artifact_no_session(self):
        """Test download without active session"""
        # Create client without session
        client = Client()
        
        response = client.get(f'{self.download_url}fake-id/')
        
        self.assertEqual(response.status_code, 404)


class TestDocumentViewUpload(BaseTestCase):
    """Test DocumentView upload_document endpoint"""
    
    def setUp(self):
        super().setUp()
        self.upload_url = '/documents/upload/'
        self.file_generator = TestFileGenerator()
    
    @patch('apps.documents.views.CELERY_AVAILABLE', False)
    def test_upload_document_success(self):
        """Test successful document upload"""
        test_file = self.file_generator.create_pdf_file("upload_test.pdf")
        
        response = self.client.post(self.upload_url, {
            'document': test_file
        })
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('document_id', response_data)
        self.assertIn('upload_test.pdf', response_data['message'])
        
        # Check document was created
        document = Document.objects.get(id=response_data['document_id'])
        self.assertEqual(document.original_name, 'upload_test.pdf')
        self.assertEqual(document.document_type, 'pdf')
        self.assertEqual(document.status, 'ready')
    
    def test_upload_document_no_file(self):
        """Test upload without file"""
        response = self.client.post(self.upload_url, {})
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('No file provided', response_data['error'])
    
    def test_upload_document_invalid_type(self):
        """Test upload with invalid file type"""
        invalid_file = self.file_generator.create_invalid_file("malicious.exe")
        
        response = self.client.post(self.upload_url, {
            'document': invalid_file
        })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('not allowed', response_data['error'])
    
    def test_upload_document_exceeds_limit(self):
        """Test upload when document limit is exceeded"""
        # Create max number of documents
        for i in range(settings.MAX_DOCUMENTS_PER_SESSION):
            self.create_test_document(f"existing{i}.pdf", "pdf", "ready")
        
        test_file = self.file_generator.create_pdf_file("overflow.pdf")
        
        response = self.client.post(self.upload_url, {
            'document': test_file
        })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('Maximum', response_data['error'])
    
    def test_upload_document_exceeds_size_limit(self):
        """Test upload when session size limit is exceeded"""
        # Create documents that total near the limit
        large_file = self.file_generator.create_large_file("large.pdf", size_mb=50)
        
        response = self.client.post(self.upload_url, {
            'document': large_file
        })
        
        self.assertEqual(response.status_code, 200)  # First large file should work
        
        # Second large file should exceed limit
        another_large_file = self.file_generator.create_large_file("another_large.pdf", size_mb=60)
        
        response = self.client.post(self.upload_url, {
            'document': another_large_file
        })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('storage limit', response_data['error'])
    
    @patch('apps.documents.views.CELERY_AVAILABLE', True)
    @patch('apps.documents.views.process_document_async')
    def test_upload_document_with_celery(self, mock_process_async):
        """Test upload with Celery processing"""
        # Mock Celery task
        mock_task = MagicMock()
        mock_task.id = 'process_task_123'
        mock_process_async.delay.return_value = mock_task
        
        test_file = self.file_generator.create_pdf_file("celery_test.pdf")
        
        response = self.client.post(self.upload_url, {
            'document': test_file
        })
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['task_id'], 'process_task_123')
        
        # Check that document has task ID and processing status
        document = Document.objects.get(id=response_data['document_id'])
        self.assertEqual(document.task_id, 'process_task_123')
        self.assertEqual(document.status, 'processing')
    
    def test_upload_document_invalid_method(self):
        """Test upload with invalid HTTP method"""
        response = self.client.get(self.upload_url)
        
        self.assertEqual(response.status_code, 405)


class TestDocumentViewStatus(BaseTestCase):
    """Test DocumentView document_status endpoint"""
    
    def setUp(self):
        super().setUp()
        self.document = self.create_test_document("status_test.pdf", "pdf", "ready")
        self.status_url = f'/documents/status/{self.document.id}/'
    
    def test_document_status_success(self):
        """Test successful document status retrieval"""
        response = self.client.get(self.status_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['id'], str(self.document.id))
        self.assertEqual(response_data['name'], 'status_test.pdf')
        self.assertEqual(response_data['status'], 'ready')
        self.assertEqual(response_data['file_size'], 1024)
        self.assertIn('uploaded_at', response_data)
    
    def test_document_status_not_found(self):
        """Test status for non-existent document"""
        fake_id = '12345678-1234-5678-9012-123456789012'
        
        response = self.client.get(f'/documents/status/{fake_id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_document_status_wrong_session(self):
        """Test status for document from different session"""
        # Create document in different session
        other_session = Session.objects.create(
            session_key='other_session',
            session_data='{}'
        )
        other_doc_session = DocumentSession.objects.create(session=other_session)
        other_document = Document.objects.create(
            session=other_doc_session,
            original_name='other.pdf',
            file_path='other_session/other.pdf',
            document_type='pdf',
            file_size=1024,
            status='ready'
        )
        
        response = self.client.get(f'/documents/status/{other_document.id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_document_status_invalid_method(self):
        """Test status with invalid HTTP method"""
        response = self.client.post(self.status_url)
        
        self.assertEqual(response.status_code, 405)


class TestDocumentViewDelete(BaseTestCase):
    """Test DocumentView delete_document endpoint"""
    
    def setUp(self):
        super().setUp()
        self.document = self.create_test_document("delete_test.pdf", "pdf", "ready")
        self.delete_url = f'/documents/delete/{self.document.id}/'
    
    @patch('apps.documents.storage.SessionFileStorage')
    def test_delete_document_success(self, mock_storage_class):
        """Test successful document deletion"""
        # Mock storage
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        
        # Store document ID before deletion
        document_id = self.document.id
        
        response = self.client.delete(self.delete_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        
        # Check document was deleted
        self.assertFalse(Document.objects.filter(id=document_id).exists())
        
        # Check storage delete was called
        mock_storage.delete.assert_called_once()
    
    def test_delete_document_not_found(self):
        """Test deletion of non-existent document"""
        fake_id = '12345678-1234-5678-9012-123456789012'
        
        response = self.client.delete(f'/documents/delete/{fake_id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_delete_document_wrong_session(self):
        """Test deletion of document from different session"""
        # Create document in different session
        other_session = Session.objects.create(
            session_key='other_session',
            session_data='{}'
        )
        other_doc_session = DocumentSession.objects.create(session=other_session)
        other_document = Document.objects.create(
            session=other_doc_session,
            original_name='other.pdf',
            file_path='other_session/other.pdf',
            document_type='pdf',
            file_size=1024,
            status='ready'
        )
        
        response = self.client.delete(f'/documents/delete/{other_document.id}/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_delete_document_updates_session_totals(self):
        """Test that deleting document updates session totals"""
        # Create additional document
        doc2 = self.create_test_document("second.pdf", "pdf", "ready")
        
        # Get initial totals
        self.doc_session.refresh_from_db()
        initial_count = self.doc_session.document_count
        initial_size = self.doc_session.total_size
        
        response = self.client.delete(self.delete_url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check updated totals
        self.doc_session.refresh_from_db()
        self.assertEqual(self.doc_session.document_count, initial_count - 1)
        self.assertEqual(self.doc_session.total_size, initial_size - 1024)


class TestDocumentViewList(BaseTestCase):
    """Test DocumentView list_documents endpoint"""
    
    def setUp(self):
        super().setUp()
        self.list_url = '/documents/list/'
    
    def test_list_documents_success(self):
        """Test successful document listing"""
        # Create test documents
        doc1 = self.create_test_document("list1.pdf", "pdf", "ready")
        doc2 = self.create_test_document("list2.xlsx", "xlsx", "processing")
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['total_count'], 2)
        self.assertEqual(len(response_data['documents']), 2)
        self.assertEqual(response_data['max_documents'], settings.MAX_DOCUMENTS_PER_SESSION)
        
        # Check document details
        document_names = [doc['name'] for doc in response_data['documents']]
        self.assertIn('list1.pdf', document_names)
        self.assertIn('list2.xlsx', document_names)
    
    def test_list_documents_empty(self):
        """Test listing with no documents"""
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['total_count'], 0)
        self.assertEqual(len(response_data['documents']), 0)
    
    def test_list_documents_no_session(self):
        """Test listing without session"""
        # Create client without session
        client = Client()
        
        response = client.get(self.list_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['documents'], [])


class TestDocumentViewSessionInfo(BaseTestCase):
    """Test DocumentView session_info endpoint"""
    
    def setUp(self):
        super().setUp()
        self.session_info_url = '/documents/session_info/'
    
    @patch('apps.documents.session_manager.SessionManager')
    def test_session_info_success(self, mock_session_manager_class):
        """Test successful session info retrieval"""
        # Mock session manager
        mock_manager = MagicMock()
        mock_manager.get_session_info.return_value = {
            'session_key': self.session.session_key,
            'document_count': 2,
            'total_size': 2048,
            'max_documents': 20
        }
        mock_session_manager_class.return_value = mock_manager
        
        response = self.client.get(self.session_info_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('session_info', response_data)
        self.assertEqual(response_data['session_info']['document_count'], 2)
    
    def test_session_info_no_session(self):
        """Test session info without active session"""
        # Create client without session
        client = Client()
        
        response = client.get(self.session_info_url)
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('No active session', response_data['error'])


class TestDocumentViewCleanup(BaseTestCase):
    """Test DocumentView cleanup_session endpoint"""
    
    def setUp(self):
        super().setUp()
        self.cleanup_url = '/documents/cleanup/'
    
    @patch('apps.documents.session_manager.SessionManager')
    def test_cleanup_session_success(self, mock_session_manager_class):
        """Test successful session cleanup"""
        # Mock session manager
        mock_manager = MagicMock()
        mock_session_manager_class.return_value = mock_manager
        
        response = self.client.post(self.cleanup_url)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        
        self.assertEqual(response_data['status'], 'success')
        self.assertIn('cleaned up', response_data['message'])
        
        # Check cleanup was called
        mock_manager.cleanup_session.assert_called_once_with(force=False)
    
    def test_cleanup_session_no_session(self):
        """Test cleanup without active session"""
        # Create client without session
        client = Client()
        
        response = client.post(self.cleanup_url)
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('No active session', response_data['error'])
    
    def test_cleanup_session_invalid_method(self):
        """Test cleanup with invalid HTTP method"""
        response = self.client.get(self.cleanup_url)
        
        self.assertEqual(response.status_code, 405)


class TestHTMXInteg
process_request.return_value = {
            'result': 'HTMX response from agent',
            'artifacts': []
        }
        mock_orchestrator_class.return_value = mock_orchestrator
        
        response = self.client.post('/send/', {
            'message': 'Test HTMX message'
        }, **self.htmx_headers)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HTMX response from agent')
    
    def test_htmx_file_upload_progress(self):
        """Test HTMX file upload with progress indication"""
        test_file = TestFileGenerator.create_pdf_file("htmx_test.pdf")
        
        response = self.client.post('/send/', {
            'message': 'Upload with HTMX',
            'files': [test_file]
        }, **self.htmx_headers)
        
        self.assertEqual(response.status_code, 200)
        
        # Should return partial template for file upload
        document = Document.objects.filter(original_name='htmx_test.pdf').first()
        self.assertIsNotNone(document)
    
    @patch('apps.chat.views.CELERY_AVAILABLE', True)
    @patch('apps.chat.views.run_agent_task_async')
    def test_htmx_async_task_polling(self, mock_async_task):
        """Test HTMX polling for async task status"""
        # Mock async task
        mock_task = MagicMock()
        mock_task.id = 'htmx_task_123'
        mock_async_task.delay.return_value = mock_task
        
        # Create test message with task
        message = self.create_test_message("assistant", "Processing...", task_id="htmx_task_123")
        
        response = self.client.get(f'/task_status/htmx_task_123/', **self.htmx_headers)
        
        # Should return partial template suitable for HTMX swapping
        self.assertEqual(response.status_code, 200)


class TestViewErrorHandling(BaseTestCase):
    """Test error handling in views"""
    
    def test_send_message_database_error(self):
        """Test send_message handles database errors gracefully"""
        with patch('apps.chat.models.Message.objects.create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            response = self.client.post('/send/', {
                'message': 'This will cause an error'
            })
            
            self.assertEqual(response.status_code, 500)
            response_data = json.loads(response.content)
            self.assertIn('error', response_data)
    
    def test_upload_document_storage_error(self):
        """Test upload handles storage errors gracefully"""
        with patch('apps.documents.storage.SessionFileStorage.save') as mock_save:
            mock_save.side_effect = Exception("Storage error")
            
            test_file = TestFileGenerator.create_pdf_file("error_test.pdf")
            
            response = self.client.post('/documents/upload/', {
                'document': test_file
            })
            
            self.assertEqual(response.status_code, 500)
            response_data = json.loads(response.content)
            self.assertIn('Upload failed', response_data['error'])
    
    def test_document_status_invalid_uuid(self):
        """Test document status with invalid UUID"""
        response = self.client.get('/documents/status/invalid-uuid/')
        
        self.assertEqual(response.status_code, 404)
    
    def test_delete_document_storage_cleanup_failure(self):
        """Test delete document handles storage cleanup failure"""
        document = self.create_test_document("cleanup_fail.pdf", "pdf", "ready")
        
        with patch('apps.documents.storage.SessionFileStorage.delete') as mock_delete:
            mock_delete.side_effect = Exception("Cleanup failed")
            
            response = self.client.delete(f'/documents/delete/{document.id}/')
            
            # Should still succeed despite cleanup failure
            self.assertEqual(response.status_code, 200)
            
            # Document should still be deleted from database
            self.assertFalse(Document.objects.filter(id=document.id).exists())


class TestViewPermissions(BaseTestCase):
    """Test view permission and access controls"""
    
    def test_cross_session_document_access_denied(self):
        """Test that users cannot access documents from other sessions"""
        # Create document in another session
        other_session = Session.objects.create(
            session_key='other_user_session',
            session_data='{}'
        )
        other_doc_session = DocumentSession.objects.create(session=other_session)
        other_document = Document.objects.create(
            session=other_doc_session,
            original_name='private.pdf',
            file_path='other_session/private.pdf',
            document_type='pdf',
            file_size=1024,
            status='ready'
        )
        
        # Try to access from current session
        response = self.client.get(f'/documents/status/{other_document.id}/')
        self.assertEqual(response.status_code, 404)
        
        response = self.client.delete(f'/documents/delete/{other_document.id}/')
        self.assertEqual(response.status_code, 404)
    
    def test_cross_session_artifact_access_denied(self):
        """Test that users cannot download artifacts from other sessions"""
        # Create artifact in another session
        other_session = Session.objects.create(
            session_key='other_artifact_session',
            session_data='{}'
        )
        other_doc_session = DocumentSession.objects.create(session=other_session)
        other_conversation = Conversation.objects.create(session=other_doc_session)
        other_message = Message.objects.create(
            conversation=other_conversation,
            role='assistant',
            content='Private file'
        )
        
        other_artifact = Artifact.objects.create(
            message=other_message,
            file_path='/tmp/private.pdf',
            file_name='private.pdf',
            file_type='application/pdf',
            file_size=1024,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Try to download from current session
        response = self.client.get(f'/download/{other_artifact.id}/')
        self.assertEqual(response.status_code, 404)


class TestViewSessionManagement(BaseTestCase):
    """Test session management in views"""
    
    def test_view_creates_session_when_needed(self):
        """Test that views create sessions when they don't exist"""
        # Create client without session
        client = Client()
        
        response = client.get('/')
        
        self.assertEqual(response.status_code, 200)
        
        # Session should be created
        session_key = client.session.session_key
        self.assertIsNotNone(session_key)
        
        # DocumentSession should be created
        doc_session = DocumentSession.objects.filter(
            session__session_key=session_key
        ).first()
        self.assertIsNotNone(doc_session)
    
    def test_view_handles_expired_session(self):
        """Test that views handle expired sessions gracefully"""
        # Create expired session
        expired_session = Session.objects.create(
            session_key='expired_session',
            session_data='{}',
            expire_date=timezone.now() - timedelta(days=1)
        )
        
        # Try to use expired session
        client = Client()
        client.session = client.session.__class__(session_key='expired_session')
        
        response = client.get('/')
        
        # Should handle gracefully and create new session
        self.assertEqual(response.status_code, 200)
    
    def test_view_updates_session_activity(self):
        """Test that views update session activity timestamps"""
        # Get initial conversation
        conversation = self.conversation
        initial_activity = conversation.last_activity
        
        # Make request that should update activity
        response = self.client.post('/send/', {
            'message': 'Update activity test'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check that activity was updated
        conversation.refresh_from_db()
        self.assertGreater(conversation.last_activity, initial_activity)


class TestViewContentNegotiation(BaseTestCase):
    """Test content negotiation and response formats"""
    
    def test_json_response_format(self):
        """Test that API endpoints return proper JSON"""
        response = self.client.get('/documents/list/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Should be valid JSON
        response_data = json.loads(response.content)
        self.assertIsInstance(response_data, dict)
    
    def test_html_response_format(self):
        """Test that template endpoints return proper HTML"""
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])
    
    def test_file_download_response_format(self):
        """Test that file downloads return proper content type"""
        # Create test artifact
        message = self.create_test_message("assistant", "Here's your file")
        artifact = Artifact.objects.create(
            message=message,
            file_path='/tmp/test.pdf',
            file_name='test.pdf',
            file_type='application/pdf',
            file_size=1024,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        with patch('apps.chat.downloads.ArtifactDownloader') as mock_downloader_class:
            mock_downloader = MagicMock()
            mock_response = HttpResponse(
                b'test content',
                content_type='application/pdf'
            )
            mock_response['Content-Disposition'] = 'attachment; filename="test.pdf"'
            mock_downloader.download_artifact.return_value = mock_response
            mock_downloader_class.return_value = mock_downloader
            
            response = self.client.get(f'/download/{artifact.id}/')
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn('attachment', response['Content-Disposition'])


class TestViewValidation(BaseTestCase):
    """Test input validation in views"""
    
    def test_upload_file_size_validation(self):
        """Test file size validation on upload"""
        # Create file larger than allowed
        large_file = TestFileGenerator.create_large_file("huge.pdf", size_mb=100)
        
        with patch('django.conf.settings.MAX_FILE_SIZE', 10 * 1024 * 1024):  # 10MB limit
            response = self.client.post('/documents/upload/', {
                'document': large_file
            })
            
            self.assertEqual(response.status_code, 400)
            response_data = json.loads(response.content)
            self.assertIn('too large', response_data['error'])
    
    def test_message_content_validation(self):
        """Test message content validation"""
        # Test empty message
        response = self.client.post('/send/', {
            'message': ''
        })
        
        # Should still work (empty messages allowed for file-only uploads)
        self.assertEqual(response.status_code, 200)
        
        # Test very long message
        long_message = 'x' * 10000
        response = self.client.post('/send/', {
            'message': long_message
        })
        
        # Should work (no length limit enforced at view level)
        self.assertEqual(response.status_code, 200)
    
    def test_file_type_validation(self):
        """Test file type validation"""
        # Test invalid file type
        invalid_file = TestFileGenerator.create_invalid_file("script.js")
        
        response = self.client.post('/documents/upload/', {
            'document': invalid_file
        })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertIn('not allowed', response_data['error'])


if __name__ == '__main__':
    import unittest
    unittest.main()