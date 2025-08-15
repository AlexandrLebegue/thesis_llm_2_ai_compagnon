from django.contrib.sessions.models import Session
from django.conf import settings
from django.utils import timezone
from apps.documents.models import DocumentSession, Document
from apps.documents.storage import SessionFileStorage
from pathlib import Path
import logging
from datetime import timedelta
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SessionManager:
    """Manage document sessions with limit enforcement and cleanup"""
    
    def __init__(self, session_key: str):
        self.session_key = session_key
        self._doc_session = None
        self._storage = None
    
    @property
    def doc_session(self) -> DocumentSession:
        """Get or create document session"""
        if self._doc_session is None:
            session_obj, _ = Session.objects.get_or_create(session_key=self.session_key)
            self._doc_session, created = DocumentSession.objects.get_or_create(
                session=session_obj
            )
        return self._doc_session
    
    @property
    def storage(self) -> SessionFileStorage:
        """Get session file storage"""
        if self._storage is None:
            self._storage = SessionFileStorage(session_id=self.session_key)
        return self._storage
    
    def can_add_document(self, file_size: int) -> Tuple[bool, str]:
        """Check if document can be added to session"""
        current_count = Document.objects.filter(conversation__session=self.doc_session).count()
        current_size = self.doc_session.total_size
        
        # Check document count limit
        if current_count >= settings.MAX_DOCUMENTS_PER_SESSION:
            return False, f"Maximum {settings.MAX_DOCUMENTS_PER_SESSION} documents allowed per session"
        
        # Check size limit (100MB per session)
        max_session_size = 100 * 1024 * 1024  # 100MB
        if current_size + file_size > max_session_size:
            return False, f"Session storage limit exceeded (100MB max, current: {current_size//1024//1024}MB)"
        
        # Check individual file size limit
        if file_size > settings.MAX_FILE_SIZE:
            return False, f"File too large (max: {settings.MAX_FILE_SIZE//1024//1024}MB)"
        
        return True, ""
    
    def add_document(self, file, document_type: str) -> Document:
        """Add document to session with validation"""
        # Validate limits
        can_add, error_msg = self.can_add_document(file.size)
        if not can_add:
            raise ValueError(error_msg)
        
        # Get or create active conversation for this session
        from apps.chat.models import Conversation
        conversation = Conversation.objects.filter(
            session=self.doc_session,
            is_active=True
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                session=self.doc_session,
                title='Main Conversation',
                is_active=True
            )
        
        # Create document record
        document = Document.objects.create(
            conversation=conversation,
            original_name=file.name,
            file_size=file.size,
            document_type=document_type,
            status='pending'
        )
        
        try:
            # Save file to storage
            file_path = self.storage.save(file.name, file)
            document.file_path = file_path
            document.save()
            
            # Update session totals
            self.update_session_totals()
            
            return document
            
        except Exception as e:
            # Clean up on failure
            document.delete()
            raise e
    
    def remove_document(self, document_id: str) -> bool:
        """Remove document from session"""
        try:
            document = Document.objects.get(
                id=document_id,
                conversation__session=self.doc_session
            )
            
            # Delete file from storage
            try:
                self.storage.delete(document.file_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {document.file_path}: {str(e)}")
            
            # Delete document record
            document.delete()
            
            # Update session totals
            self.update_session_totals()
            
            return True
            
        except Document.DoesNotExist:
            return False
    
    def update_session_totals(self):
        """Update document count and total size for session"""
        documents = Document.objects.filter(conversation__session=self.doc_session)
        self.doc_session.document_count = documents.count()
        self.doc_session.total_size = sum(doc.file_size for doc in documents)
        self.doc_session.save()
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information and statistics"""
        documents = Document.objects.filter(conversation__session=self.doc_session)
        
        status_counts = {}
        for status_choice in Document.STATUS_CHOICES:
            status = status_choice[0]
            status_counts[status] = documents.filter(status=status).count()
        
        type_counts = {}
        for type_choice in Document.DOCUMENT_TYPES:
            doc_type = type_choice[0]
            type_counts[doc_type] = documents.filter(document_type=doc_type).count()
        
        return {
            'session_key': self.session_key,
            'document_count': self.doc_session.document_count,
            'total_size': self.doc_session.total_size,
            'max_documents': settings.MAX_DOCUMENTS_PER_SESSION,
            'remaining_slots': settings.MAX_DOCUMENTS_PER_SESSION - self.doc_session.document_count,
            'status_breakdown': status_counts,
            'type_breakdown': type_counts,
            'created_at': self.doc_session.created_at,
            'storage_path': str(self.storage.base_path)
        }
    
    def cleanup_session(self, force: bool = False):
        """Clean up session files and data"""
        try:
            # Delete all files in storage
            if self.storage.base_path.exists():
                for file_path in self.storage.base_path.rglob('*'):
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                        except Exception as e:
                            logger.warning(f"Failed to delete {file_path}: {str(e)}")
                
                # Remove directory if empty
                try:
                    self.storage.base_path.rmdir()
                except OSError:
                    pass  # Directory not empty or doesn't exist
            
            # Delete document records
            Document.objects.filter(conversation__session=self.doc_session).delete()
            
            # Delete document session
            if force:
                self.doc_session.delete()
            else:
                self.doc_session.document_count = 0
                self.doc_session.total_size = 0
                self.doc_session.save()
            
            logger.info(f"Cleaned up session {self.session_key}")
            
        except Exception as e:
            logger.error(f"Error cleaning up session {self.session_key}: {str(e)}")
    
    @classmethod
    def cleanup_expired_sessions(cls, hours: int = 24):
        """Clean up sessions older than specified hours"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        expired_sessions = DocumentSession.objects.filter(
            created_at__lt=cutoff_time
        )
        
        cleaned_count = 0
        for doc_session in expired_sessions:
            try:
                session_manager = cls(doc_session.session.session_key)
                session_manager.cleanup_session(force=True)
                cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning expired session {doc_session.session.session_key}: {str(e)}")
        
        logger.info(f"Cleaned up {cleaned_count} expired sessions")
        return cleaned_count
    
    @classmethod
    def cleanup_orphaned_files(cls):
        """Clean up files without corresponding database records"""
        temp_root = settings.TEMP_FILE_ROOT
        if not temp_root.exists():
            return 0
        
        cleaned_count = 0
        
        # Get all session directories
        for session_dir in temp_root.iterdir():
            if not session_dir.is_dir():
                continue
            
            session_key = session_dir.name
            
            try:
                # Check if session exists in database
                Session.objects.get(session_key=session_key)
                DocumentSession.objects.get(session__session_key=session_key)
                
                # Session exists, check individual files
                for file_path in session_dir.rglob('*'):
                    if file_path.is_file():
                        # Check if file has corresponding document record
                        relative_path = file_path.relative_to(temp_root)
                        if not Document.objects.filter(file_path=str(relative_path)).exists():
                            try:
                                file_path.unlink()
                                cleaned_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete orphaned file {file_path}: {str(e)}")
                
            except (Session.DoesNotExist, DocumentSession.DoesNotExist):
                # Session doesn't exist, delete entire directory
                try:
                    for file_path in session_dir.rglob('*'):
                        if file_path.is_file():
                            file_path.unlink()
                            cleaned_count += 1
                    session_dir.rmdir()
                except Exception as e:
                    logger.warning(f"Failed to delete orphaned session directory {session_dir}: {str(e)}")
        
        logger.info(f"Cleaned up {cleaned_count} orphaned files")
        return cleaned_count
    
    def get_document_list(self) -> List[Dict[str, Any]]:
        """Get list of documents in session with details"""
        documents = Document.objects.filter(conversation__session=self.doc_session).order_by('-uploaded_at')
        
        document_list = []
        for doc in documents:
            document_list.append({
                'id': str(doc.id),
                'name': doc.original_name,
                'type': doc.document_type,
                'size': doc.file_size,
                'size_mb': round(doc.file_size / (1024 * 1024), 2),
                'status': doc.status,
                'status_display': doc.get_status_display(),
                'uploaded_at': doc.uploaded_at,
                'processed_at': doc.processed_at,
                'summary': doc.summary,
                'error_message': doc.error_message,
                'has_error': bool(doc.error_message),
                'is_ready': doc.status == 'ready'
            })
        
        return document_list