from celery import shared_task
from django.utils import timezone
from apps.documents.models import Document, DocumentContext
from apps.documents.parsers import PDFParser, ExcelParser, WordParser
from apps.documents.summarizer import DocumentSummarizer
from apps.documents.storage import SessionFileStorage
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_document_async(self, document_id: str, regenerate_summary: bool = False):
    """
    Process document asynchronously: parse content and generate summary
    
    Args:
        document_id: UUID of document to process
        regenerate_summary: Whether to regenerate summary for already processed document
    
    Returns:
        dict: Processing result with status and metadata
    """
    try:
        logger.info(f"Starting document processing for document {document_id}")
        
        # Get document
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            error_msg = f"Document {document_id} not found"
            logger.error(error_msg)
            return {'status': 'error', 'error': error_msg}
        
        # Update status
        document.status = 'processing'
        document.save()
        
        try:
            # Get file path
            storage = SessionFileStorage(session_id=document.session.session.session_key)
            file_path = storage.path(document.file_path)
            
            # Parse document based on type
            parser_result = _parse_document(document.document_type, file_path)
            
            if parser_result['status'] == 'error':
                document.status = 'error'
                document.error_message = parser_result['error']
                document.save()
                return parser_result
            
            # Generate summary
            summary_result = _generate_summary(
                document.document_type, 
                parser_result['content'],
                regenerate=regenerate_summary
            )
            
            if summary_result['status'] == 'error':
                document.status = 'error'
                document.error_message = summary_result['error']
                document.save()
                return summary_result
            
            # Update document with results
            document.summary = summary_result['summary']
            document.metadata = {
                **parser_result.get('metadata', {}),
                'processing_time': (timezone.now() - document.uploaded_at).total_seconds(),
                'content_length': len(str(parser_result['content'])),
                'summary_length': len(summary_result['summary'])
            }
            document.status = 'ready'
            document.processed_at = timezone.now()
            document.error_message = ''
            document.save()
            
            # Update session context
            try:
                context_obj, created = DocumentContext.objects.get_or_create(
                    session=document.session
                )
                context_obj.update_context()
            except Exception as e:
                logger.warning(f"Failed to update context for document {document_id}: {str(e)}")
            
            logger.info(f"Successfully processed document {document_id}")
            
            return {
                'status': 'success',
                'document_id': document_id,
                'summary': summary_result['summary'],
                'metadata': document.metadata
            }
            
        except Exception as e:
            error_msg = f"Error processing document {document_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            document.status = 'error'
            document.error_message = str(e)
            document.save()
            
            # Retry logic
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying document processing for {document_id} (attempt {self.request.retries + 1})")
                raise self.retry(countdown=60 * (2 ** self.request.retries))
            
            return {'status': 'error', 'error': error_msg}
    
    except Exception as e:
        error_msg = f"Fatal error processing document {document_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'status': 'error', 'error': error_msg}


def _parse_document(document_type: str, file_path: str) -> Dict[str, Any]:
    """Parse document content based on type"""
    try:
        if document_type == 'pdf':
            content = PDFParser.parse(file_path)
        elif document_type == 'xlsx':
            content = ExcelParser.parse(file_path)
        elif document_type == 'docx':
            content = WordParser.parse(file_path)
        else:
            return {
                'status': 'error',
                'error': f'Unsupported document type: {document_type}'
            }
        
        return {
            'status': 'success',
            'content': content,
            'metadata': getattr(content, 'metadata', {})
        }
        
    except Exception as e:
        logger.error(f"Error parsing {document_type} document {file_path}: {str(e)}")
        return {
            'status': 'error',
            'error': f'Failed to parse document: {str(e)}'
        }


def _generate_summary(document_type: str, content: Any, regenerate: bool = False) -> Dict[str, Any]:
    """Generate document summary"""
    try:
        summarizer = DocumentSummarizer()
        
        if document_type == 'pdf':
            summary = summarizer.summarize_pdf_content(content)
        elif document_type == 'xlsx':
            summary = summarizer.summarize_excel_content(content)
        elif document_type == 'docx':
            summary = summarizer.summarize_word_content(content)
        else:
            return {
                'status': 'error',
                'error': f'Cannot summarize document type: {document_type}'
            }
        
        return {
            'status': 'success',
            'summary': summary
        }
        
    except Exception as e:
        logger.error(f"Error generating summary for {document_type}: {str(e)}")
        return {
            'status': 'error',
            'error': f'Failed to generate summary: {str(e)}'
        }


@shared_task
def cleanup_expired_documents():
    """Clean up expired documents and files"""
    from apps.documents.session_manager import SessionManager
    from apps.documents.storage import TempFileManager
    from django.conf import settings
    
    try:
        # Clean up expired sessions
        expired_count = SessionManager.cleanup_expired_sessions(
            hours=getattr(settings, 'TEMP_FILE_CLEANUP_HOURS', 24)
        )
        
        # Clean up orphaned files
        orphaned_count = SessionManager.cleanup_orphaned_files()
        
        # Clean up expired temp files
        temp_count = TempFileManager.cleanup_expired_files(
            hours=getattr(settings, 'TEMP_FILE_CLEANUP_HOURS', 24)
        )
        
        logger.info(f"Cleanup completed: {expired_count} expired sessions, {orphaned_count} orphaned files, {temp_count} temp files")
        
        return {
            'status': 'success',
            'expired_sessions': expired_count,
            'orphaned_files': orphaned_count,
            'temp_files': temp_count
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True, max_retries=2)
def batch_process_documents(self, document_ids: list):
    """Process multiple documents in batch"""
    results = []
    
    for document_id in document_ids:
        try:
            result = process_document_async.delay(document_id)
            results.append({
                'document_id': document_id,
                'task_id': result.id,
                'status': 'queued'
            })
        except Exception as e:
            logger.error(f"Failed to queue document {document_id}: {str(e)}")
            results.append({
                'document_id': document_id,
                'status': 'error',
                'error': str(e)
            })
    
    return {
        'status': 'success',
        'batch_size': len(document_ids),
        'results': results
    }


@shared_task
def update_document_context(session_id: str):
    """Update document context for a session"""
    try:
        from django.contrib.sessions.models import Session
        from apps.documents.models import DocumentSession, DocumentContext
        
        # Get session
        session_obj = Session.objects.get(session_key=session_id)
        doc_session = DocumentSession.objects.get(session=session_obj)
        
        # Update context
        context_obj, created = DocumentContext.objects.get_or_create(
            session=doc_session
        )
        context_obj.update_context()
        
        logger.info(f"Updated context for session {session_id}")
        
        return {
            'status': 'success',
            'session_id': session_id,
            'document_count': context_obj.context_data.get('document_count', 0)
        }
        
    except Exception as e:
        logger.error(f"Error updating context for session {session_id}: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def generate_session_report(session_id: str):
    """Generate processing report for a session"""
    try:
        from apps.documents.session_manager import SessionManager
        
        session_manager = SessionManager(session_id)
        session_info = session_manager.get_session_info()
        document_list = session_manager.get_document_list()
        
        # Calculate processing statistics
        total_processed = sum(1 for doc in document_list if doc['status'] == 'ready')
        total_errors = sum(1 for doc in document_list if doc['status'] == 'error')
        total_size_mb = session_info['total_size'] / (1024 * 1024)
        
        report = {
            'session_id': session_id,
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_documents': session_info['document_count'],
                'processed_successfully': total_processed,
                'processing_errors': total_errors,
                'total_size_mb': round(total_size_mb, 2),
                'processing_rate': round(total_processed / max(session_info['document_count'], 1) * 100, 1)
            },
            'documents': document_list,
            'session_info': session_info
        }
        
        logger.info(f"Generated report for session {session_id}")
        return {'status': 'success', 'report': report}
        
    except Exception as e:
        logger.error(f"Error generating report for session {session_id}: {str(e)}")
        return {'status': 'error', 'error': str(e)}