from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.conf import settings
from django.db import models
from apps.documents.models import DocumentSession, Document, DocumentContext
from apps.documents.storage import SessionFileStorage
from apps.documents.validators import validate_file_upload
# Conditional import for development without Celery
try:
    from tasks.document_tasks import process_document_async
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    process_document_async = None
import json
import logging

logger = logging.getLogger(__name__)

class DocumentView:
    """Document upload and management views"""
    
    @staticmethod
    @require_http_methods(["POST"])
    def upload_document(request):
        """Handle document upload"""
        try:
            # Get or create session
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            
            session_obj, _ = Session.objects.get_or_create(session_key=session_key)
            doc_session, created = DocumentSession.objects.get_or_create(
                session=session_obj
            )
            
            # Get uploaded file
            uploaded_file = request.FILES.get('document')
            if not uploaded_file:
                return JsonResponse({'error': 'No file provided'}, status=400)
            
            # Validate file
            try:
                validate_file_upload(uploaded_file)
            except ValueError as e:
                return JsonResponse({'error': str(e)}, status=400)
            
            # Check document limit
            if doc_session.documents.count() >= settings.MAX_DOCUMENTS_PER_SESSION:
                return JsonResponse({
                    'error': f'Maximum {settings.MAX_DOCUMENTS_PER_SESSION} documents allowed per session'
                }, status=400)
            
            # Check total size limit (100MB per session)
            total_size = doc_session.total_size + uploaded_file.size
            if total_size > 100 * 1024 * 1024:  # 100MB limit
                return JsonResponse({
                    'error': 'Session storage limit exceeded (100MB max)'
                }, status=400)
            
            # Create document record
            document = Document.objects.create(
                session=doc_session,
                original_name=uploaded_file.name,
                file_size=uploaded_file.size,
                document_type=uploaded_file.name.split('.')[-1].lower(),
                status='pending'
            )
            
            # Save file using session storage
            storage = SessionFileStorage(session_id=session_key)
            file_path = storage.save(uploaded_file.name, uploaded_file)
            document.file_path = file_path
            document.save()
            
            # Update session totals
            doc_session.document_count = doc_session.documents.count()
            doc_session.total_size = doc_session.documents.aggregate(
                total=models.Sum('file_size')
            )['total'] or 0
            doc_session.save()
            
            # Queue document processing (if Celery is available)
            task = None
            if CELERY_AVAILABLE and process_document_async:
                task = process_document_async.delay(str(document.id))
                document.task_id = task.id
                document.status = 'processing'
                document.save()
                message = f'Document {uploaded_file.name} uploaded and processing started'
            else:
                # Fallback: mark as ready for development
                document.status = 'ready'
                document.save()
                message = f'Document {uploaded_file.name} uploaded successfully'
            
            response_data = {
                'status': 'success',
                'document_id': str(document.id),
                'message': message
            }
            
            if task:
                response_data['task_id'] = task.id
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            return JsonResponse({'error': 'Upload failed'}, status=500)
    
    @staticmethod
    @require_http_methods(["GET"])
    def document_status(request, document_id):
        """Get document processing status"""
        try:
            document = get_object_or_404(Document, id=document_id)
            
            # Check if document belongs to current session
            session_key = request.session.session_key
            if not session_key or document.session.session.session_key != session_key:
                return JsonResponse({'error': 'Document not found'}, status=404)
            
            return JsonResponse({
                'id': str(document.id),
                'name': document.original_name,
                'status': document.status,
                'file_size': document.file_size,
                'uploaded_at': document.uploaded_at.isoformat(),
                'processed_at': document.processed_at.isoformat() if document.processed_at else None,
                'summary': document.summary,
                'error_message': document.error_message
            })
            
        except Exception as e:
            logger.error(f"Error getting document status: {str(e)}")
            return JsonResponse({'error': 'Status check failed'}, status=500)
    
    @staticmethod
    @require_http_methods(["DELETE"])
    def delete_document(request, document_id):
        """Delete a document from session"""
        try:
            document = get_object_or_404(Document, id=document_id)
            
            # Check if document belongs to current session
            session_key = request.session.session_key
            if not session_key or document.session.session.session_key != session_key:
                return JsonResponse({'error': 'Document not found'}, status=404)
            
            # Delete file from storage
            try:
                storage = SessionFileStorage(session_id=session_key)
                storage.delete(document.file_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {document.file_path}: {str(e)}")
            
            # Update session totals before deleting
            doc_session = document.session
            doc_session.document_count = doc_session.documents.exclude(id=document.id).count()
            doc_session.total_size = doc_session.documents.exclude(id=document.id).aggregate(
                total=models.Sum('file_size')
            )['total'] or 0
            doc_session.save()
            
            # Delete document record
            document.delete()
            
            # Update context
            try:
                context_obj = DocumentContext.objects.get(session=doc_session)
                context_obj.update_context()
            except DocumentContext.DoesNotExist:
                pass
            
            return JsonResponse({
                'status': 'success',
                'message': f'Document deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            return JsonResponse({'error': 'Delete failed'}, status=500)
    
    @staticmethod
    @require_http_methods(["GET"])
    def download_document(request, document_id):
        """Download the original document file"""
        try:
            document = get_object_or_404(Document, id=document_id)
            
            # Check if document belongs to current session
            session_key = request.session.session_key
            if not session_key or document.session.session.session_key != session_key:
                return JsonResponse({'error': 'Document not found'}, status=404)
            
            # Get file from storage
            storage = SessionFileStorage(session_id=session_key)
            
            try:
                file_obj = storage.open(document.file_path)
                
                # Create response with file content
                response = HttpResponse(file_obj.read(), content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename="{document.original_name}"'
                response['Content-Length'] = document.file_size
                
                file_obj.close()
                return response
                
            except FileNotFoundError:
                logger.error(f"File not found for document {document_id}: {document.file_path}")
                return JsonResponse({'error': 'File not found'}, status=404)
            
        except Exception as e:
            logger.error(f"Error downloading document: {str(e)}")
            return JsonResponse({'error': 'Download failed'}, status=500)
    
    @staticmethod
    @require_http_methods(["GET"])
    def list_documents(request):
        """List all documents in current session"""
        try:
            session_key = request.session.session_key
            if not session_key:
                # Check if this is an HTMX request
                if request.headers.get('HX-Request'):
                    return render(request, 'chat/partials/document_list.html', {'documents': []})
                return JsonResponse({'documents': []})
            
            try:
                session_obj = Session.objects.get(session_key=session_key)
                doc_session = DocumentSession.objects.get(session=session_obj)
            except (Session.DoesNotExist, DocumentSession.DoesNotExist):
                # Check if this is an HTMX request
                if request.headers.get('HX-Request'):
                    return render(request, 'chat/partials/document_list.html', {'documents': []})
                return JsonResponse({'documents': []})
            
            documents = doc_session.documents.all()
            
            # Check if this is an HTMX request
            if request.headers.get('HX-Request'):
                return render(request, 'chat/partials/document_list.html', {'documents': documents})
            
            # For non-HTMX requests, return JSON
            document_list = []
            for doc in documents:
                document_list.append({
                    'id': str(doc.id),
                    'name': doc.original_name,
                    'type': doc.document_type,
                    'size': doc.file_size,
                    'status': doc.status,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
                    'summary': doc.summary,
                    'error_message': doc.error_message
                })
            
            return JsonResponse({
                'documents': document_list,
                'total_count': len(document_list),
                'total_size': doc_session.total_size,
                'max_documents': settings.MAX_DOCUMENTS_PER_SESSION
            })
            
        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            if request.headers.get('HX-Request'):
                return render(request, 'chat/partials/document_list.html', {'documents': [], 'error': 'Failed to load documents'})
            return JsonResponse({'error': 'Failed to list documents'}, status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def regenerate_summary(request, document_id):
        """Regenerate summary for a document"""
        try:
            document = get_object_or_404(Document, id=document_id)
            
            # Check if document belongs to current session
            session_key = request.session.session_key
            if not session_key or document.session.session.session_key != session_key:
                return JsonResponse({'error': 'Document not found'}, status=404)
            
            # Only regenerate for ready documents
            if document.status != 'ready':
                return JsonResponse({
                    'error': 'Document must be processed before regenerating summary'
                }, status=400)
            
            # Queue reprocessing (if Celery is available)
            if CELERY_AVAILABLE and process_document_async:
                task = process_document_async.delay(str(document.id), regenerate_summary=True)
                document.task_id = task.id
                document.status = 'processing'
                document.save()
            else:
                return JsonResponse({
                    'error': 'Async processing not available in development mode'
                }, status=503)
            
            return JsonResponse({
                'status': 'success',
                'task_id': task.id,
                'message': 'Summary regeneration started'
            })
            
        except Exception as e:
            logger.error(f"Error regenerating summary: {str(e)}")
            return JsonResponse({'error': 'Summary regeneration failed'}, status=500)
    
    @staticmethod
    @require_http_methods(["GET"])
    def session_info(request):
        """Get session information and statistics"""
        try:
            from apps.documents.session_manager import SessionManager
            
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_manager = SessionManager(session_key)
            session_info = session_manager.get_session_info()
            
            return JsonResponse({
                'status': 'success',
                'session_info': session_info
            })
            
        except Exception as e:
            logger.error(f"Error getting session info: {str(e)}")
            return JsonResponse({'error': 'Failed to get session info'}, status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def cleanup_session(request):
        """Clean up current session documents and files"""
        try:
            from apps.documents.session_manager import SessionManager
            
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_manager = SessionManager(session_key)
            session_manager.cleanup_session(force=False)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Session cleaned up successfully'
            })
            
        except Exception as e:
            logger.error(f"Error cleaning up session: {str(e)}")
            return JsonResponse({'error': 'Session cleanup failed'}, status=500)