import pytest
import tempfile
import shutil
from pathlib import Path
from django.test import TestCase, Client
from django.contrib.sessions.models import Session
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from unittest.mock import patch, MagicMock
import io
from apps.documents.models import DocumentSession, Document, DocumentContext
from apps.chat.models import Conversation, Message, Artifact
from apps.documents.session_manager import SessionManager
from apps.documents.storage import SessionFileStorage


class TestFileGenerator:
    """Generate test files for different document types"""
    
    @staticmethod
    def create_pdf_file(filename="test.pdf", content="Test PDF content"):
        """Create a simple PDF-like file"""
        pdf_content = f"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length {len(content)} >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n({content}) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000125 00000 n\n0000000185 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{len(pdf_content) - 20}\n%%EOF"
        return SimpleUploadedFile(filename, pdf_content.encode('utf-8'), content_type='application/pdf')
    
    @staticmethod
    def create_excel_file(filename="test.xlsx"):
        """Create a simple XLSX-like file (ZIP structure)"""
        # This is a minimal ZIP file structure that mimics an XLSX file
        zip_content = b'PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00\x08\x02[Content_Types].xmlUT\x05\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00PK\x01\x02\x14\x03\x14\x00\x00\x00\x08\x00\x00\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00\x08\x02\x00\x00\x00\x00\x00\x00\x00\x00\xa4\x81\x00\x00\x00\x00[Content_Types].xmlUT\x05\x00\x01\x00\x00\x00\x00PK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x00I\x00\x00\x00=\x00\x00\x00\x00\x00'
        return SimpleUploadedFile(filename, zip_content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    @staticmethod
    def create_word_file(filename="test.docx"):
        """Create a simple DOCX-like file (ZIP structure)"""
        # This is a minimal ZIP file structure that mimics a DOCX file
        zip_content = b'PK\x03\x04\x14\x00\x00\x00\x08\x00\x00\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00\x08\x02[Content_Types].xmlUT\x05\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00PK\x01\x02\x14\x03\x14\x00\x00\x00\x08\x00\x00\x00!\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00\x08\x02\x00\x00\x00\x00\x00\x00\x00\x00\xa4\x81\x00\x00\x00\x00[Content_Types].xmlUT\x05\x00\x01\x00\x00\x00\x00PK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x00I\x00\x00\x00=\x00\x00\x00\x00\x00'
        return SimpleUploadedFile(filename, zip_content, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    
    @staticmethod
    def create_large_file(filename="large.pdf", size_mb=5):
        """Create a large file for testing size limits"""
        content = b'A' * (size_mb * 1024 * 1024)
        return SimpleUploadedFile(filename, content, content_type='application/pdf')
    
    @staticmethod
    def create_invalid_file(filename="malicious.exe"):
        """Create an invalid file type"""
        content = b'This is not a valid document'
        return SimpleUploadedFile(filename, content, content_type='application/octet-stream')


@pytest.fixture
def file_generator():
    """Provide the file generator utility"""
    return TestFileGenerator()


@pytest.fixture
def test_session():
    """Create a test session"""
    session = Session.objects.create(
        session_key='test_session_key_12345',
        session_data='{}',
    )
    yield session
    session.delete()


@pytest.fixture
def document_session(test_session):
    """Create a test document session"""
    doc_session = DocumentSession.objects.create(
        session=test_session,
        document_count=0,
        total_size=0
    )
    yield doc_session
    doc_session.delete()


@pytest.fixture
def conversation(document_session):
    """Create a test conversation"""
    conv = Conversation.objects.create(session=document_session)
    yield conv
    conv.delete()


@pytest.fixture
def test_client():
    """Provide Django test client"""
    return Client()


@pytest.fixture
def authenticated_client(test_client, test_session):
    """Provide an authenticated test client with session"""
    test_client.session = test_client.session
    test_client.session.session_key = test_session.session_key
    test_client.session.save()
    return test_client


@pytest.fixture
def temp_storage_path():
    """Create temporary storage directory"""
    temp_dir = tempfile.mkdtemp(prefix='test_storage_')
    original_temp_root = settings.TEMP_FILE_ROOT
    settings.TEMP_FILE_ROOT = Path(temp_dir)
    yield Path(temp_dir)
    # Cleanup
    settings.TEMP_FILE_ROOT = original_temp_root
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def session_manager(test_session, temp_storage_path):
    """Create a test session manager"""
    manager = SessionManager(test_session.session_key)
    yield manager
    # Cleanup will be handled by temp_storage_path fixture


@pytest.fixture
def sample_document(document_session, file_generator, temp_storage_path):
    """Create a sample document for testing"""
    doc = Document.objects.create(
        session=document_session,
        original_name="sample.pdf",
        file_path="test_session_key_12345/sample.pdf",
        document_type="pdf",
        file_size=1024,
        status="ready",
        summary="Test document summary",
        metadata={"pages": 1, "title": "Test Document"}
    )
    
    # Create actual file in storage
    storage = SessionFileStorage(session_id=document_session.session.session_key)
    test_file = file_generator.create_pdf_file("sample.pdf")
    storage.save("sample.pdf", test_file)
    
    yield doc
    doc.delete()


@pytest.fixture
def sample_message(conversation):
    """Create a sample message for testing"""
    message = Message.objects.create(
        conversation=conversation,
        role='user',
        content='Test message content',
        artifacts=[]
    )
    yield message
    message.delete()


@pytest.fixture
def mock_celery():
    """Mock Celery for testing without Redis dependency"""
    with patch('apps.chat.views.CELERY_AVAILABLE', False), \
         patch('apps.documents.views.CELERY_AVAILABLE', False), \
         patch('tasks.document_tasks.process_document_async', None), \
         patch('tasks.agent_tasks.run_agent_task_async', None):
        yield


@pytest.fixture
def mock_smolagents():
    """Mock SmolAgents for testing without external dependencies"""
    mock_agent = MagicMock()
    mock_agent.run.return_value = "Test agent response"
    
    with patch('apps.agents.orchestrator.InferenceClientModel') as mock_model, \
         patch('apps.agents.orchestrator.ToolCallingAgent') as mock_agent_class:
        mock_agent_class.return_value = mock_agent
        yield mock_agent


@pytest.fixture
def mock_parsers():
    """Mock document parsers for testing without file dependencies"""
    
    def mock_pdf_parse(file_path):
        from apps.documents.parsers.pdf_parser import PDFContent
        return PDFContent(
            text="Mock PDF content",
            tables=[],
            metadata={"pages": 1, "title": "Mock PDF"},
            page_count=1
        )
    
    def mock_excel_parse(file_path):
        from apps.documents.parsers.excel_parser import ExcelContent
        return {
            'sheets': {'Sheet1': [['A1', 'B1'], ['A2', 'B2']]},
            'metadata': {'sheet_count': 1}
        }
    
    def mock_word_parse(file_path):
        from apps.documents.parsers.word_parser import WordContent
        return {
            'text': "Mock Word content",
            'metadata': {'paragraphs': 1}
        }
    
    with patch('apps.documents.parsers.pdf_parser.PDFParser.parse', side_effect=mock_pdf_parse), \
         patch('apps.documents.parsers.excel_parser.ExcelParser.parse', side_effect=mock_excel_parse), \
         patch('apps.documents.parsers.word_parser.WordParser.parse', side_effect=mock_word_parse):
        yield


@pytest.fixture
def test_artifacts_data():
    """Provide test artifact data"""
    return [
        {
            'id': 'artifact_1',
            'file_path': '/tmp/test_artifact_1.pdf',
            'file_name': 'generated_chart.pdf',
            'file_type': 'application/pdf',
            'file_size': 2048
        },
        {
            'id': 'artifact_2',
            'file_path': '/tmp/test_artifact_2.xlsx',
            'file_name': 'modified_spreadsheet.xlsx',
            'file_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'file_size': 4096
        }
    ]


# Custom test case class for shared functionality
class BaseTestCase(TestCase):
    """Base test case with common utilities"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix='test_')
        self.original_temp_root = settings.TEMP_FILE_ROOT
        settings.TEMP_FILE_ROOT = Path(self.temp_dir)
        
        # Create test session
        self.session = Session.objects.create(
            session_key='test_session_12345',
            session_data='{}'
        )
        
        # Create document session
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
        
        # Create conversation
        self.conversation = Conversation.objects.create(
            session=self.doc_session
        )
        
        # Set up test client with session
        self.client = Client()
        session = self.client.session
        session.session_key = self.session.session_key
        session.save()
    
    def tearDown(self):
        """Clean up test environment"""
        settings.TEMP_FILE_ROOT = self.original_temp_root
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_document(self, filename="test.pdf", doc_type="pdf", status="ready"):
        """Helper to create test documents"""
        return Document.objects.create(
            session=self.doc_session,
            original_name=filename,
            file_path=f"{self.session.session_key}/{filename}",
            document_type=doc_type,
            file_size=1024,
            status=status,
            summary=f"Test {doc_type} document",
            metadata={"test": True}
        )
    
    def create_test_message(self, role="user", content="Test message"):
        """Helper to create test messages"""
        return Message.objects.create(
            conversation=self.conversation,
            role=role,
            content=content,
            artifacts=[]
        )


# Database setup for tests
@pytest.fixture(scope='session')
def django_db_setup():
    """Set up test database configuration"""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }


# Disable migrations for faster tests
@pytest.fixture(scope='session')
def django_db_migrations_disable():
    """Disable migrations for faster test execution"""
    settings.MIGRATION_MODULES = {
        'auth': None,
        'contenttypes': None,
        'sessions': None,
        'messages': None,
        'admin': None,
        'chat': None,
        'documents': None,
        'agents': None,
    }


# Test settings override
@pytest.fixture
def test_settings():
    """Override settings for testing"""
    original_settings = {
        'MAX_FILE_SIZE': settings.MAX_FILE_SIZE,
        'MAX_DOCUMENTS_PER_SESSION': settings.MAX_DOCUMENTS_PER_SESSION,
        'ALLOWED_FILE_EXTENSIONS': settings.ALLOWED_FILE_EXTENSIONS,
    }
    
    # Set test-friendly values
    settings.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB for tests
    settings.MAX_DOCUMENTS_PER_SESSION = 5  # Lower limit for tests
    
    yield
    
    # Restore original settings
    for key, value in original_settings.items():
        setattr(settings, key, value)