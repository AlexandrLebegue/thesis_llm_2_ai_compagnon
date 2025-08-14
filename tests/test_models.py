import pytest
import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from unittest.mock import patch, MagicMock
from tests.conftest import BaseTestCase

# Import models to test
from apps.documents.models import DocumentSession, Document, DocumentContext
from apps.chat.models import Conversation, Message, Artifact


class TestDocumentSessionModel(BaseTestCase):
    """Test DocumentSession model functionality"""
    
    def test_document_session_creation(self):
        """Test creating a DocumentSession"""
        session = Session.objects.create(
            session_key='test_session_123',
            session_data='{}'
        )
        
        doc_session = DocumentSession.objects.create(
            session=session,
            document_count=0,
            total_size=0
        )
        
        self.assertEqual(doc_session.session, session)
        self.assertEqual(doc_session.document_count, 0)
        self.assertEqual(doc_session.total_size, 0)
        self.assertIsNotNone(doc_session.created_at)
    
    def test_document_session_str_representation(self):
        """Test string representation of DocumentSession"""
        session = Session.objects.create(
            session_key='test_key_456',
            session_data='{}'
        )
        
        doc_session = DocumentSession.objects.create(
            session=session,
            document_count=5,
            total_size=1024
        )
        
        expected_str = f"DocumentSession test_key_456 (5 docs)"
        self.assertEqual(str(doc_session), expected_str)
    
    def test_document_session_unique_constraint(self):
        """Test that session relationship is unique"""
        session = Session.objects.create(
            session_key='unique_test',
            session_data='{}'
        )
        
        # Create first DocumentSession
        DocumentSession.objects.create(session=session)
        
        # Attempt to create second DocumentSession with same session should fail
        with self.assertRaises(IntegrityError):
            DocumentSession.objects.create(session=session)
    
    def test_document_session_cascade_delete(self):
        """Test that DocumentSession is deleted when Session is deleted"""
        session = Session.objects.create(
            session_key='cascade_test',
            session_data='{}'
        )
        
        doc_session = DocumentSession.objects.create(session=session)
        doc_session_id = doc_session.id
        
        # Delete the session
        session.delete()
        
        # DocumentSession should be deleted too
        self.assertFalse(
            DocumentSession.objects.filter(id=doc_session_id).exists()
        )


class TestDocumentModel(BaseTestCase):
    """Test Document model functionality"""
    
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            session_key='doc_test_session',
            session_data='{}'
        )
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
    
    def test_document_creation(self):
        """Test creating a Document"""
        document = Document.objects.create(
            session=self.doc_session,
            original_name='test.pdf',
            file_path='session123/test.pdf',
            document_type='pdf',
            file_size=1024,
            status='pending'
        )
        
        self.assertEqual(document.session, self.doc_session)
        self.assertEqual(document.original_name, 'test.pdf')
        self.assertEqual(document.document_type, 'pdf')
        self.assertEqual(document.file_size, 1024)
        self.assertEqual(document.status, 'pending')
        self.assertIsNotNone(document.id)
        self.assertIsInstance(document.id, uuid.UUID)
    
    def test_document_str_representation(self):
        """Test string representation of Document"""
        document = Document.objects.create(
            session=self.doc_session,
            original_name='report.xlsx',
            file_path='session123/report.xlsx',
            document_type='xlsx',
            file_size=2048,
            status='ready'
        )
        
        expected_str = "report.xlsx (Ready)"
        self.assertEqual(str(document), expected_str)
    
    def test_document_status_choices(self):
        """Test document status choices validation"""
        valid_statuses = ['pending', 'processing', 'ready', 'error']
        
        for status in valid_statuses:
            document = Document.objects.create(
                session=self.doc_session,
                original_name=f'test_{status}.pdf',
                file_path=f'session123/test_{status}.pdf',
                document_type='pdf',
                file_size=1024,
                status=status
            )
            self.assertEqual(document.status, status)
    
    def test_document_type_choices(self):
        """Test document type choices validation"""
        valid_types = ['pdf', 'xlsx', 'docx']
        
        for doc_type in valid_types:
            document = Document.objects.create(
                session=self.doc_session,
                original_name=f'test.{doc_type}',
                file_path=f'session123/test.{doc_type}',
                document_type=doc_type,
                file_size=1024,
                status='pending'
            )
            self.assertEqual(document.document_type, doc_type)
    
    def test_document_default_values(self):
        """Test document default field values"""
        document = Document.objects.create(
            session=self.doc_session,
            original_name='test.pdf',
            file_path='session123/test.pdf',
            document_type='pdf',
            file_size=1024
        )
        
        self.assertEqual(document.status, 'pending')
        self.assertEqual(document.summary, '')
        self.assertEqual(document.error_message, '')
        self.assertEqual(document.metadata, {})
        self.assertIsNone(document.processed_at)
    
    def test_document_ordering(self):
        """Test document ordering by upload date"""
        # Create documents with different upload times
        doc1 = Document.objects.create(
            session=self.doc_session,
            original_name='first.pdf',
            file_path='session123/first.pdf',
            document_type='pdf',
            file_size=1024
        )
        
        doc2 = Document.objects.create(
            session=self.doc_session,
            original_name='second.pdf',
            file_path='session123/second.pdf',
            document_type='pdf',
            file_size=1024
        )
        
        documents = list(Document.objects.all())
        
        # Should be ordered by most recent first (-uploaded_at)
        self.assertEqual(documents[0], doc2)  # Most recent first
        self.assertEqual(documents[1], doc1)
    
    def test_document_cascade_delete(self):
        """Test that Document is deleted when DocumentSession is deleted"""
        document = Document.objects.create(
            session=self.doc_session,
            original_name='test.pdf',
            file_path='session123/test.pdf',
            document_type='pdf',
            file_size=1024
        )
        
        document_id = document.id
        
        # Delete the document session
        self.doc_session.delete()
        
        # Document should be deleted too
        self.assertFalse(
            Document.objects.filter(id=document_id).exists()
        )


class TestDocumentContextModel(BaseTestCase):
    """Test DocumentContext model functionality"""
    
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            session_key='context_test_session',
            session_data='{}'
        )
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
    
    def test_document_context_creation(self):
        """Test creating a DocumentContext"""
        context = DocumentContext.objects.create(
            session=self.doc_session,
            context_data={'test': 'data'}
        )
        
        self.assertEqual(context.session, self.doc_session)
        self.assertEqual(context.context_data, {'test': 'data'})
        self.assertIsNotNone(context.last_updated)
    
    def test_document_context_str_representation(self):
        """Test string representation of DocumentContext"""
        context = DocumentContext.objects.create(
            session=self.doc_session,
            context_data={}
        )
        
        expected_str = f"Context for {self.doc_session}"
        self.assertEqual(str(context), expected_str)
    
    def test_document_context_unique_constraint(self):
        """Test that session relationship is unique"""
        # Create first DocumentContext
        DocumentContext.objects.create(session=self.doc_session)
        
        # Attempt to create second DocumentContext with same session should fail
        with self.assertRaises(IntegrityError):
            DocumentContext.objects.create(session=self.doc_session)
    
    def test_update_context_method(self):
        """Test the update_context method"""
        # Create some test documents
        doc1 = Document.objects.create(
            session=self.doc_session,
            original_name='doc1.pdf',
            file_path='session123/doc1.pdf',
            document_type='pdf',
            file_size=1024,
            status='ready',
            summary='First document summary',
            metadata={'pages': 5}
        )
        
        doc2 = Document.objects.create(
            session=self.doc_session,
            original_name='doc2.xlsx',
            file_path='session123/doc2.xlsx',
            document_type='xlsx',
            file_size=2048,
            status='ready',
            summary='Second document summary',
            metadata={'sheets': 3}
        )
        
        # Create document that's not ready (should be excluded)
        Document.objects.create(
            session=self.doc_session,
            original_name='doc3.docx',
            file_path='session123/doc3.docx',
            document_type='docx',
            file_size=512,
            status='pending'
        )
        
        context = DocumentContext.objects.create(
            session=self.doc_session,
            context_data={}
        )
        
        # Update context
        context.update_context()
        
        # Check updated context data
        self.assertEqual(context.context_data['document_count'], 2)
        self.assertEqual(len(context.context_data['documents']), 2)
        
        # Check first document in context
        doc1_context = context.context_data['documents'][0]
        self.assertEqual(doc1_context['name'], 'doc1.pdf')
        self.assertEqual(doc1_context['type'], 'pdf')
        self.assertEqual(doc1_context['summary'], 'First document summary')
        self.assertEqual(doc1_context['metadata'], {'pages': 5})
    
    def test_update_context_empty_documents(self):
        """Test update_context with no ready documents"""
        context = DocumentContext.objects.create(
            session=self.doc_session,
            context_data={}
        )
        
        context.update_context()
        
        self.assertEqual(context.context_data['document_count'], 0)
        self.assertEqual(context.context_data['documents'], [])
    
    def test_document_context_cascade_delete(self):
        """Test that DocumentContext is deleted when DocumentSession is deleted"""
        context = DocumentContext.objects.create(
            session=self.doc_session,
            context_data={}
        )
        
        context_id = context.id
        
        # Delete the document session
        self.doc_session.delete()
        
        # DocumentContext should be deleted too
        self.assertFalse(
            DocumentContext.objects.filter(id=context_id).exists()
        )


class TestConversationModel(BaseTestCase):
    """Test Conversation model functionality"""
    
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            session_key='conv_test_session',
            session_data='{}'
        )
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
    
    def test_conversation_creation(self):
        """Test creating a Conversation"""
        conversation = Conversation.objects.create(
            session=self.doc_session
        )
        
        self.assertEqual(conversation.session, self.doc_session)
        self.assertIsNotNone(conversation.id)
        self.assertIsInstance(conversation.id, uuid.UUID)
        self.assertIsNotNone(conversation.started_at)
        self.assertIsNotNone(conversation.last_activity)
    
    def test_conversation_str_representation(self):
        """Test string representation of Conversation"""
        conversation = Conversation.objects.create(
            session=self.doc_session
        )
        
        expected_str = f"Conversation {conversation.id} (started {conversation.started_at.strftime('%Y-%m-%d %H:%M')})"
        self.assertEqual(str(conversation), expected_str)
    
    def test_conversation_ordering(self):
        """Test conversation ordering by last activity"""
        conv1 = Conversation.objects.create(session=self.doc_session)
        conv2 = Conversation.objects.create(session=self.doc_session)
        
        conversations = list(Conversation.objects.all())
        
        # Should be ordered by most recent activity first (-last_activity)
        self.assertEqual(conversations[0], conv2)  # Most recent first
        self.assertEqual(conversations[1], conv1)
    
    def test_conversation_cascade_delete(self):
        """Test that Conversation is deleted when DocumentSession is deleted"""
        conversation = Conversation.objects.create(session=self.doc_session)
        conversation_id = conversation.id
        
        # Delete the document session
        self.doc_session.delete()
        
        # Conversation should be deleted too
        self.assertFalse(
            Conversation.objects.filter(id=conversation_id).exists()
        )


class TestMessageModel(BaseTestCase):
    """Test Message model functionality"""
    
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            session_key='msg_test_session',
            session_data='{}'
        )
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
        self.conversation = Conversation.objects.create(
            session=self.doc_session
        )
    
    def test_message_creation(self):
        """Test creating a Message"""
        message = Message.objects.create(
            conversation=self.conversation,
            role='user',
            content='Hello, this is a test message'
        )
        
        self.assertEqual(message.conversation, self.conversation)
        self.assertEqual(message.role, 'user')
        self.assertEqual(message.content, 'Hello, this is a test message')
        self.assertIsNotNone(message.id)
        self.assertIsInstance(message.id, uuid.UUID)
        self.assertIsNotNone(message.created_at)
    
    def test_message_str_representation(self):
        """Test string representation of Message"""
        message = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='This is a long message that should be truncated in the string representation'
        )
        
        expected_str = "Assistant: This is a long message that should be truncated ..."
        self.assertEqual(str(message), expected_str)
    
    def test_message_role_choices(self):
        """Test message role choices validation"""
        valid_roles = ['user', 'assistant', 'system']
        
        for role in valid_roles:
            message = Message.objects.create(
                conversation=self.conversation,
                role=role,
                content=f'Test message from {role}'
            )
            self.assertEqual(message.role, role)
    
    def test_message_default_values(self):
        """Test message default field values"""
        message = Message.objects.create(
            conversation=self.conversation,
            role='user',
            content='Test message'
        )
        
        self.assertEqual(message.task_id, '')
        self.assertEqual(message.task_status, '')
        self.assertEqual(message.artifacts, [])
    
    def test_message_ordering(self):
        """Test message ordering by creation time"""
        msg1 = Message.objects.create(
            conversation=self.conversation,
            role='user',
            content='First message'
        )
        
        msg2 = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Second message'
        )
        
        messages = list(Message.objects.all())
        
        # Should be ordered by creation time (created_at)
        self.assertEqual(messages[0], msg1)  # First created first
        self.assertEqual(messages[1], msg2)
    
    def test_message_with_task_info(self):
        """Test message with task tracking information"""
        message = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Processing your request...',
            task_id='task_123',
            task_status='PENDING'
        )
        
        self.assertEqual(message.task_id, 'task_123')
        self.assertEqual(message.task_status, 'PENDING')
    
    def test_message_with_artifacts(self):
        """Test message with artifacts data"""
        artifacts_data = [
            {'type': 'chart', 'path': '/tmp/chart.png'},
            {'type': 'file', 'path': '/tmp/output.xlsx'}
        ]
        
        message = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Here are your generated files',
            artifacts=artifacts_data
        )
        
        self.assertEqual(message.artifacts, artifacts_data)
    
    def test_message_cascade_delete(self):
        """Test that Message is deleted when Conversation is deleted"""
        message = Message.objects.create(
            conversation=self.conversation,
            role='user',
            content='Test message'
        )
        
        message_id = message.id
        
        # Delete the conversation
        self.conversation.delete()
        
        # Message should be deleted too
        self.assertFalse(
            Message.objects.filter(id=message_id).exists()
        )


class TestArtifactModel(BaseTestCase):
    """Test Artifact model functionality"""
    
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            session_key='artifact_test_session',
            session_data='{}'
        )
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
        self.conversation = Conversation.objects.create(
            session=self.doc_session
        )
        self.message = Message.objects.create(
            conversation=self.conversation,
            role='assistant',
            content='Generated file for you'
        )
    
    def test_artifact_creation(self):
        """Test creating an Artifact"""
        expires_at = timezone.now() + timedelta(hours=24)
        
        artifact = Artifact.objects.create(
            message=self.message,
            file_path='/tmp/test_chart.png',
            file_name='test_chart.png',
            file_type='image/png',
            file_size=2048,
            expires_at=expires_at
        )
        
        self.assertEqual(artifact.message, self.message)
        self.assertEqual(artifact.file_path, '/tmp/test_chart.png')
        self.assertEqual(artifact.file_name, 'test_chart.png')
        self.assertEqual(artifact.file_type, 'image/png')
        self.assertEqual(artifact.file_size, 2048)
        self.assertEqual(artifact.expires_at, expires_at)
        self.assertIsNotNone(artifact.id)
        self.assertIsInstance(artifact.id, uuid.UUID)
        self.assertIsNotNone(artifact.created_at)
    
    def test_artifact_str_representation(self):
        """Test string representation of Artifact"""
        expires_at = timezone.now() + timedelta(hours=24)
        
        artifact = Artifact.objects.create(
            message=self.message,
            file_path='/tmp/report.xlsx',
            file_name='monthly_report.xlsx',
            file_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            file_size=4096,
            expires_at=expires_at
        )
        
        expected_str = "monthly_report.xlsx (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)"
        self.assertEqual(str(artifact), expected_str)
    
    def test_artifact_cascade_delete(self):
        """Test that Artifact is deleted when Message is deleted"""
        expires_at = timezone.now() + timedelta(hours=24)
        
        artifact = Artifact.objects.create(
            message=self.message,
            file_path='/tmp/test.pdf',
            file_name='test.pdf',
            file_type='application/pdf',
            file_size=1024,
            expires_at=expires_at
        )
        
        artifact_id = artifact.id
        
        # Delete the message
        self.message.delete()
        
        # Artifact should be deleted too
        self.assertFalse(
            Artifact.objects.filter(id=artifact_id).exists()
        )


class TestModelRelationships(BaseTestCase):
    """Test relationships between models"""
    
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            session_key='relationship_test_session',
            session_data='{}'
        )
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
    
    def test_document_session_to_documents_relationship(self):
        """Test DocumentSession to Documents relationship"""
        # Create documents
        doc1 = Document.objects.create(
            session=self.doc_session,
            original_name='doc1.pdf',
            file_path='session123/doc1.pdf',
            document_type='pdf',
            file_size=1024
        )
        
        doc2 = Document.objects.create(
            session=self.doc_session,
            original_name='doc2.xlsx',
            file_path='session123/doc2.xlsx',
            document_type='xlsx',
            file_size=2048
        )
        
        # Test relationship
        documents = self.doc_session.documents.all()
        self.assertEqual(documents.count(), 2)
        self.assertIn(doc1, documents)
        self.assertIn(doc2, documents)
    
    def test_document_session_to_conversations_relationship(self):
        """Test DocumentSession to Conversations relationship"""
        # Create conversations
        conv1 = Conversation.objects.create(session=self.doc_session)
        conv2 = Conversation.objects.create(session=self.doc_session)
        
        # Test relationship
        conversations = self.doc_session.conversations.all()
        self.assertEqual(conversations.count(), 2)
        self.assertIn(conv1, conversations)
        self.assertIn(conv2, conversations)
    
    def test_conversation_to_messages_relationship(self):
        """Test Conversation to Messages relationship"""
        conversation = Conversation.objects.create(session=self.doc_session)
        
        # Create messages
        msg1 = Message.objects.create(
            conversation=conversation,
            role='user',
            content='Hello'
        )
        
        msg2 = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Hi there!'
        )
        
        # Test relationship
        messages = conversation.messages.all()
        self.assertEqual(messages.count(), 2)
        self.assertIn(msg1, messages)
        self.assertIn(msg2, messages)
    
    def test_message_to_artifacts_relationship(self):
        """Test Message to Artifacts relationship"""
        conversation = Conversation.objects.create(session=self.doc_session)
        message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Generated files'
        )
        
        expires_at = timezone.now() + timedelta(hours=24)
        
        # Create artifacts
        artifact1 = Artifact.objects.create(
            message=message,
            file_path='/tmp/chart.png',
            file_name='chart.png',
            file_type='image/png',
            file_size=1024,
            expires_at=expires_at
        )
        
        artifact2 = Artifact.objects.create(
            message=message,
            file_path='/tmp/report.pdf',
            file_name='report.pdf',
            file_type='application/pdf',
            file_size=2048,
            expires_at=expires_at
        )
        
        # Test relationship
        artifacts = message.generated_artifacts.all()
        self.assertEqual(artifacts.count(), 2)
        self.assertIn(artifact1, artifacts)
        self.assertIn(artifact2, artifacts)


class TestModelValidation(BaseTestCase):
    """Test model field validation and constraints"""
    
    def setUp(self):
        super().setUp()
        self.session = Session.objects.create(
            session_key='validation_test_session',
            session_data='{}'
        )
        self.doc_session = DocumentSession.objects.create(
            session=self.session,
            document_count=0,
            total_size=0
        )
    
    def test_document_file_size_validation(self):
        """Test that file_size must be positive"""
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Document.objects.create(
                    session=self.doc_session,
                    original_name='test.pdf',
                    file_path='session123/test.pdf',
                    document_type='pdf',
                    file_size=-1  # Negative size should fail
                )
    
    def test_artifact_file_size_validation(self):
        """Test that artifact file_size must be positive"""
        conversation = Conversation.objects.create(session=self.doc_session)
        message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content='Test'
        )
        
        expires_at = timezone.now() + timedelta(hours=24)
        
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Artifact.objects.create(
                    message=message,
                    file_path='/tmp/test.pdf',
                    file_name='test.pdf',
                    file_type='application/pdf',
                    file_size=-100,  # Negative size should fail
                    expires_at=expires_at
                )
    
    def test_required_fields(self):
        """Test that required fields cannot be null"""
        # Test Document required fields
        with self.assertRaises(IntegrityError):
            Document.objects.create(
                session=self.doc_session,
                # Missing original_name
                file_path='session123/test.pdf',
                document_type='pdf',
                file_size=1024
            )
        
        # Test Message required fields
        conversation = Conversation.objects.create(session=self.doc_session)
        
        with self.assertRaises(IntegrityError):
            Message.objects.create(
                conversation=conversation,
                role='user'
                # Missing content
            )


if __name__ == '__main__':
    import unittest
    unittest.main()