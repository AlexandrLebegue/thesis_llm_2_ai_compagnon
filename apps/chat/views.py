from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django.conf import settings
from django.db import models
from django_htmx.http import HttpResponseClientRedirect
from apps.documents.models import DocumentSession, Document, DocumentContext
from apps.chat.models import Conversation, Message, Artifact
from apps.agents.orchestrator import ChatbotOrchestrator
# Conditional imports for development without Celery
try:
    from tasks.document_tasks import process_document_async
    from tasks.agent_tasks import run_agent_task_async
    from celery.result import AsyncResult
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    process_document_async = None
    run_agent_task_async = None
    AsyncResult = None
from apps.documents.storage import SessionFileStorage
import json
import logging

logger = logging.getLogger(__name__)

class ChatView:
    """Main chat interface view"""
    
    @staticmethod
    def index(request):
        """Main chat page"""
        # Get or create document session
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        # Get or create session object
        session_obj, _ = Session.objects.get_or_create(session_key=session_key)
        doc_session, created = DocumentSession.objects.get_or_create(
            session=session_obj
        )
        
        # Get conversation
        conversation = Conversation.objects.filter(
            session=doc_session
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(session=doc_session)
        
        # Get documents and messages
        documents = doc_session.documents.all()
        messages = conversation.messages.all()
        
        context = {
            'documents': documents,
            'messages': messages,
            'max_documents': settings.MAX_DOCUMENTS_PER_SESSION,
            'current_document_count': documents.count(),
        }
        
        return render(request, 'chat/index.html', context)
    
    @staticmethod
    @require_http_methods(["POST"])
    def send_message(request):
        """Handle chat message submission"""
        try:
            # Get session and conversation
            session_obj = Session.objects.get(session_key=request.session.session_key)
            doc_session = DocumentSession.objects.get(
                session=session_obj
            )
            conversation = Conversation.objects.get(session=doc_session)
            
            # Get message and files
            message_text = request.POST.get('message', '')
            files = request.FILES.getlist('files')
            
            # Process uploaded files
            if files:
                for file in files:
                    # Check document limit
                    if doc_session.documents.count() >= settings.MAX_DOCUMENTS_PER_SESSION:
                        return JsonResponse({
                            'error': f'Maximum {settings.MAX_DOCUMENTS_PER_SESSION} documents allowed'
                        }, status=400)
                    
                    # Save document
                    document = Document.objects.create(
                        session=doc_session,
                        original_name=file.name,
                        file_size=file.size,
                        document_type=file.name.split('.')[-1].lower()
                    )
                    
                    # Save file to temp storage
                    storage = SessionFileStorage(session_id=request.session.session_key)
                    file_path = storage.save(file.name, file)
                    document.file_path = file_path
                    document.save()
                    
                    # Queue processing (if Celery is available)
                    if CELERY_AVAILABLE and process_document_async:
                        task = process_document_async.delay(document.id)
                        document.task_id = task.id
                        document.save()
                    else:
                        # Fallback: mark as ready for development
                        document.status = 'ready'
                        document.save()
            
            # Create user message (backend only - frontend already displayed it)
            user_message = Message.objects.create(
                conversation=conversation,
                role='user',
                content=message_text
            )
            
            # Get context
            context_obj, created = DocumentContext.objects.get_or_create(
                session=doc_session
            )
            context_obj.update_context()
            
            # Determine if async processing is needed
            use_async = ChatView._should_use_async(message_text, doc_session)
            
            if use_async and CELERY_AVAILABLE and run_agent_task_async:
                # Queue agent task
                task = run_agent_task_async.delay(
                    instruction=message_text,
                    context=context_obj.context_data,
                    session_id=request.session.session_key,
                    message_id=str(user_message.id)
                )
                
                # Create assistant message with task ID
                assistant_message = Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content='Processing your request...',
                    task_id=task.id,
                    task_status='PENDING'
                )
                
                # Return HTMX response with polling trigger (assistant message only)
                return render(request, 'chat/partials/message_pending.html', {
                    'message': assistant_message
                })
            
            else:
                # Create assistant message first
                assistant_message = Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content='Processing your request...',
                    artifacts=[]
                )
                
                # Process synchronously with message object
                orchestrator = ChatbotOrchestrator(session_id=request.session.session_key)
                result = orchestrator.process_request(
                    instruction=message_text,
                    context=context_obj.context_data,
                    session_id=request.session.session_key,
                    message=assistant_message
                )
                
                # Update assistant message with result
                assistant_message.content = result.get('result', 'I processed your request.')
                assistant_message.artifacts = result.get('artifacts', [])
                assistant_message.save()
                
                # Return HTMX response (assistant message only)
                return render(request, 'chat/partials/message.html', {
                    'message': assistant_message
                })
                
        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    def _should_use_async(message: str, session: DocumentSession) -> bool:
        """Determine if request should be processed asynchronously"""
        # Use async for:
        # - Multiple documents (>3)
        # - Large documents (total > 10MB)
        # - Complex operations (modify, generate charts)
        
        doc_count = session.documents.count()
        total_size = session.documents.aggregate(
            total=models.Sum('file_size')
        )['total'] or 0
        
        complex_keywords = ['modify', 'generate', 'create chart', 'analyze all']
        has_complex = any(keyword in message.lower() for keyword in complex_keywords)
        
        return doc_count > 3 or total_size > 10*1024*1024 or has_complex
    
    @staticmethod
    @require_http_methods(["GET"])
    def check_task_status(request, task_id):
        """Check status of async task"""
        try:
            if not CELERY_AVAILABLE or not AsyncResult:
                return JsonResponse({'error': 'Async processing not available'}, status=500)
            
            result = AsyncResult(task_id)
            
            if result.ready():
                message = Message.objects.get(task_id=task_id)
                
                if result.successful():
                    # Update message with result
                    task_result = result.get()
                    message.content = task_result.get('result', 'Task completed.')
                    message.artifacts = task_result.get('artifacts', [])
                    message.task_status = 'SUCCESS'
                    message.save()
                    
                    # Save artifacts
                    for artifact_data in task_result.get('artifacts', []):
                        Artifact.objects.create(
                            message=message,
                            **artifact_data
                        )
                else:
                    # Handle failure
                    message.content = f"Error: {result.info}"
                    message.task_status = 'FAILURE'
                    message.save()
                
                # Return completed message
                return render(request, 'chat/partials/message.html', {
                    'message': message
                })
            
            else:
                # Task still running, return pending status
                return render(request, 'chat/partials/message_pending.html', {
                    'message': Message.objects.get(task_id=task_id)
                })
                
        except Exception as e:
            logger.error(f"Error checking task status: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @require_http_methods(["GET"])
    def download_artifact(request, artifact_id):
        """Download artifact file"""
        try:
            from apps.chat.downloads import ArtifactDownloader
            
            # Get artifact
            artifact = Artifact.objects.get(id=artifact_id)
            
            # Check if artifact belongs to current session
            session_key = request.session.session_key
            if not session_key:
                return HttpResponse('Session not found', status=404)
            
            # Verify artifact belongs to user's session
            message_session = artifact.message.conversation.session.session.session_key
            if message_session != session_key:
                return HttpResponse('Artifact not found', status=404)
            
            # Use downloader to serve file
            downloader = ArtifactDownloader()
            return downloader.download_artifact(artifact)
            
        except Artifact.DoesNotExist:
            return HttpResponse('Artifact not found', status=404)
        except Exception as e:
            logger.error(f"Error downloading artifact {artifact_id}: {str(e)}")
            return HttpResponse('Download failed', status=500)
    
    @staticmethod
    @require_http_methods(["GET"])
    def view_artifact_inline(request, artifact_id):
        """View artifact file inline (for images in chat)"""
        try:
            from apps.chat.downloads import ArtifactDownloader
            
            # Get artifact
            artifact = Artifact.objects.get(id=artifact_id)
            
            # Check if artifact belongs to current session
            session_key = request.session.session_key
            if not session_key:
                return HttpResponse('Session not found', status=404)
            
            # Verify artifact belongs to user's session
            message_session = artifact.message.conversation.session.session.session_key
            if message_session != session_key:
                return HttpResponse('Artifact not found', status=404)
            
            # Use downloader to serve file inline
            downloader = ArtifactDownloader()
            return downloader.download_artifact(artifact, inline=True)
            
        except Artifact.DoesNotExist:
            return HttpResponse('Artifact not found', status=404)
        except Exception as e:
            logger.error(f"Error viewing artifact {artifact_id}: {str(e)}")
            return HttpResponse('View failed', status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def clear_chat(request):
        """Clear chat history for current session"""
        try:
            # Get session and conversation
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            # Delete all conversations and their messages for this session
            conversations = Conversation.objects.filter(session=doc_session)
            for conversation in conversations:
                # Delete associated artifacts first
                for message in conversation.messages.all():
                    message.generated_artifacts.all().delete()
                # Delete messages
                conversation.messages.all().delete()
            # Delete conversations
            conversations.delete()
            
            # Create a new conversation
            new_conversation = Conversation.objects.create(session=doc_session)
            
            return JsonResponse({
                'success': True,
                'message': 'Chat history cleared successfully'
            })
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return JsonResponse({'error': 'Session not found'}, status=404)
        except Exception as e:
            logger.error(f"Error clearing chat: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)