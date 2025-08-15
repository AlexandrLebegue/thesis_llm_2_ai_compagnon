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
                    message_id=str(user_message.id),
                    conversation_id=str(conversation.id)
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
                    message=assistant_message,
                    conversation_id=str(conversation.id)
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
    @require_http_methods(["GET"])
    def view_word_preview(request, artifact_id):
        """View Word document preview as HTML"""
        try:
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
            
            # Check if this is a Word document
            if not (artifact.file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    or 'word' in artifact.file_type.lower()
                    or artifact.file_name.lower().endswith('.docx')):
                return HttpResponse('Not a Word document', status=400)
            
            # Get preview HTML
            if artifact.preview_html:
                # Serve the stored preview HTML
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>Word Document Preview - {artifact.file_name}</title>
                    <style>
                        body {{
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 800px;
                            margin: 0 auto;
                            padding: 20px;
                            background-color: #f9f9f9;
                        }}
                        .preview-container {{
                            background: white;
                            padding: 30px;
                            border-radius: 8px;
                            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        }}
                        .preview-h1 {{ font-size: 2em; margin-bottom: 0.5em; color: #2c3e50; }}
                        .preview-h2 {{ font-size: 1.5em; margin-bottom: 0.5em; color: #34495e; }}
                        .preview-h3 {{ font-size: 1.2em; margin-bottom: 0.5em; color: #34495e; }}
                        .preview-paragraph {{ margin-bottom: 1em; }}
                        .preview-table {{
                            border-collapse: collapse;
                            width: 100%;
                            margin: 1em 0;
                        }}
                        .preview-table th, .preview-table td {{
                            border: 1px solid #ddd;
                            padding: 8px;
                            text-align: left;
                        }}
                        .preview-table th {{
                            background-color: #f2f2f2;
                            font-weight: bold;
                        }}
                        .preview-list {{ margin: 1em 0; padding-left: 2em; }}
                        .preview-quote {{
                            border-left: 4px solid #3498db;
                            margin: 1em 0;
                            padding-left: 1em;
                            font-style: italic;
                        }}
                        .preview-truncated {{
                            margin-top: 2em;
                            padding: 1em;
                            background-color: #f8f9fa;
                            border-left: 4px solid #007bff;
                            color: #6c757d;
                        }}
                    </style>
                </head>
                <body>
                    <div class="preview-container">
                        <h1 style="border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                            {artifact.file_name}
                        </h1>
                        {artifact.preview_html}
                    </div>
                </body>
                </html>
                """
                
                response = HttpResponse(html_content, content_type='text/html')
                # Allow iframe embedding from same origin to fix Firefox security issue
                response['X-Frame-Options'] = 'SAMEORIGIN'
                return response
            else:
                # No preview available
                return HttpResponse('''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <title>Preview Not Available</title>
                        <style>
                            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                            .message { background: #f8f9fa; padding: 20px; border-radius: 8px; display: inline-block; }
                        </style>
                    </head>
                    <body>
                        <div class="message">
                            <h2>Preview Not Available</h2>
                            <p>This Word document doesn't have a preview available.</p>
                            <p>Please download the document to view its contents.</p>
                        </div>
                    </body>
                    </html>
                ''', content_type='text/html')
                
        except Artifact.DoesNotExist:
            return HttpResponse('Artifact not found', status=404)
        except Exception as e:
            logger.error(f"Error viewing Word preview {artifact_id}: {str(e)}")
            return HttpResponse('Preview failed', status=500)
    
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