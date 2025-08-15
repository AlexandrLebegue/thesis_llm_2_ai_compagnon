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
        # Check if user is authenticated or if this should show auth modal
        show_auth_modal = not request.user.is_authenticated
        
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
        
        # Get active conversation or create one
        conversation = Conversation.objects.filter(
            session=doc_session,
            is_active=True
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                session=doc_session,
                title='Main Conversation',
                is_active=True
            )
        
        # Get documents and messages for this conversation
        documents = conversation.documents.all()
        messages = conversation.messages.all()
        conversations = doc_session.conversations.all().order_by('-last_activity')
        
        context = {
            'documents': documents,
            'messages': messages,
            'conversations': conversations,
            'active_conversation': conversation,
            'max_documents': settings.MAX_DOCUMENTS_PER_SESSION,
            'current_document_count': documents.count(),
            'show_auth_modal': show_auth_modal,
        }
        
        return render(request, 'chat/index.html', context)
    
    @staticmethod
    @require_http_methods(["POST"])
    def send_message(request):
        """Handle chat message submission"""
        try:
            # Get session and active conversation
            session_obj = Session.objects.get(session_key=request.session.session_key)
            doc_session = DocumentSession.objects.get(
                session=session_obj
            )
            
            # Get conversation ID from request or use active one
            conversation_id = request.POST.get('conversation_id')
            if conversation_id:
                conversation = Conversation.objects.get(id=conversation_id, session=doc_session)
            else:
                conversation = Conversation.objects.filter(
                    session=doc_session,
                    is_active=True
                ).first()
                if not conversation:
                    conversation = Conversation.objects.create(
                        session=doc_session,
                        title='Main Conversation',
                        is_active=True
                    )
            
            # Update conversation activity
            conversation.update_activity()
            
            # Get message and files
            message_text = request.POST.get('message', '')
            files = request.FILES.getlist('files')
            
            # Process uploaded files
            if files:
                for file in files:
                    # Check document limit per conversation
                    if conversation.documents.count() >= settings.MAX_DOCUMENTS_PER_SESSION:
                        return JsonResponse({
                            'error': f'Maximum {settings.MAX_DOCUMENTS_PER_SESSION} documents allowed per conversation'
                        }, status=400)
                    
                    # Save document to conversation
                    document = Document.objects.create(
                        conversation=conversation,
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
            
            # Get context for this conversation
            context_obj, created = DocumentContext.objects.get_or_create(
                conversation=conversation
            )
            context_obj.update_context()
            
            # Determine if async processing is needed
            use_async = ChatView._should_use_async(message_text, conversation)
            
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
    def _should_use_async(message: str, conversation: Conversation) -> bool:
        """Determine if request should be processed asynchronously"""
        # Use async for:
        # - Multiple documents (>3)
        # - Large documents (total > 10MB)
        # - Complex operations (modify, generate charts)
        
        doc_count = conversation.documents.count()
        total_size = conversation.documents.aggregate(
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
    @require_http_methods(["GET"])
    def view_excel_preview(request, artifact_id):
        """View Excel document preview as HTML"""
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
            
            # Check if this is an Excel document
            if not (artifact.file_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']
                    or 'excel' in artifact.file_type.lower()
                    or 'spreadsheet' in artifact.file_type.lower()
                    or artifact.file_name.lower().endswith(('.xlsx', '.xls'))):
                return HttpResponse('Not an Excel document', status=400)
            
            # Get preview HTML
            if artifact.preview_html:
                # Serve the stored preview HTML
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>Excel Preview - {artifact.file_name}</title>
                    <style>
                        body {{
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 1200px;
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
                        .excel-sheet-container {{
                            margin-bottom: 2em;
                        }}
                        .preview-sheet-title {{
                            font-size: 1.5em;
                            margin-bottom: 0.5em;
                            color: #2c3e50;
                            border-bottom: 2px solid #27ae60;
                            padding-bottom: 5px;
                        }}
                        .excel-sheet-stats {{
                            background-color: #f8f9fa;
                            padding: 0.5em 1em;
                            margin-bottom: 1em;
                            border-radius: 4px;
                            color: #6c757d;
                            font-size: 0.9em;
                        }}
                        .excel-table-wrapper {{
                            overflow-x: auto;
                            margin: 1em 0;
                        }}
                        .preview-excel-table {{
                            border-collapse: collapse;
                            width: 100%;
                            font-size: 0.9em;
                        }}
                        .preview-excel-header {{
                            background-color: #27ae60;
                            color: white;
                            padding: 12px 8px;
                            text-align: left;
                            font-weight: bold;
                            border: 1px solid #219a52;
                        }}
                        .preview-excel-cell {{
                            padding: 8px;
                            border: 1px solid #ddd;
                            vertical-align: top;
                        }}
                        .preview-excel-cell:nth-child(even) {{
                            background-color: #f8f9fa;
                        }}
                        .excel-tabs-container {{
                            margin-bottom: 2em;
                        }}
                        .excel-tabs-header {{
                            display: flex;
                            border-bottom: 2px solid #ddd;
                            margin-bottom: 1em;
                        }}
                        .excel-tab-button {{
                            background: #f8f9fa;
                            border: none;
                            padding: 10px 20px;
                            cursor: pointer;
                            border-top: 3px solid transparent;
                            transition: all 0.3s ease;
                        }}
                        .excel-tab-button.active {{
                            background: white;
                            border-top-color: #27ae60;
                            color: #27ae60;
                            font-weight: bold;
                        }}
                        .excel-tab-button:hover {{
                            background: #e9ecef;
                        }}
                        .excel-tab-content {{
                            display: none;
                        }}
                        .excel-tab-content.active {{
                            display: block;
                        }}
                        .preview-truncated {{
                            margin-top: 2em;
                            padding: 1em;
                            background-color: #fff3cd;
                            border-left: 4px solid #ffc107;
                            color: #856404;
                        }}
                    </style>
                    <script>
                        function switchExcelTab(tabId) {{
                            // Hide all tabs
                            const contents = document.querySelectorAll('.excel-tab-content');
                            contents.forEach(content => content.classList.remove('active'));
                            
                            // Remove active class from all buttons
                            const buttons = document.querySelectorAll('.excel-tab-button');
                            buttons.forEach(button => button.classList.remove('active'));
                            
                            // Show selected tab
                            const targetContent = document.getElementById('tab-' + tabId);
                            if (targetContent) {{
                                targetContent.classList.add('active');
                            }}
                            
                            // Activate button
                            const targetButton = document.querySelector('[data-tab="' + tabId + '"]');
                            if (targetButton) {{
                                targetButton.classList.add('active');
                            }}
                        }}
                    </script>
                </head>
                <body>
                    <div class="preview-container">
                        <h1 style="border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                            📊 {artifact.file_name}
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
                            <p>This Excel document doesn't have a preview available.</p>
                            <p>Please download the document to view its contents.</p>
                        </div>
                    </body>
                    </html>
                ''', content_type='text/html')
                
        except Artifact.DoesNotExist:
            return HttpResponse('Artifact not found', status=404)
        except Exception as e:
            logger.error(f"Error viewing Excel preview {artifact_id}: {str(e)}")
            return HttpResponse('Preview failed', status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def clear_chat(request):
        """Clear chat history for current conversation only"""
        try:
            # Get session and conversation
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            # Get the active conversation
            conversation_id = request.POST.get('conversation_id')
            if conversation_id:
                conversation = Conversation.objects.get(id=conversation_id, session=doc_session)
            else:
                conversation = Conversation.objects.filter(
                    session=doc_session,
                    is_active=True
                ).first()
                
            if not conversation:
                return JsonResponse({'error': 'No active conversation found'}, status=404)
            
            # Delete associated artifacts first
            for message in conversation.messages.all():
                message.generated_artifacts.all().delete()
            
            # Delete messages for this conversation only
            conversation.messages.all().delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Conversation cleared successfully'
            })
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return JsonResponse({'error': 'Session not found'}, status=404)
        except Conversation.DoesNotExist:
            return JsonResponse({'error': 'Conversation not found'}, status=404)
        except Exception as e:
            logger.error(f"Error clearing chat: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def create_conversation(request):
        """Create a new conversation"""
        try:
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            # Get title from request or generate one
            title = request.POST.get('title', '').strip()
            if not title:
                # Generate title based on conversation count
                count = doc_session.conversations.count() + 1
                title = f'Conversation {count}'
            
            # Deactivate current active conversation
            Conversation.objects.filter(
                session=doc_session,
                is_active=True
            ).update(is_active=False)
            
            # Create new conversation
            conversation = Conversation.objects.create(
                session=doc_session,
                title=title,
                is_active=True
            )
            
            # Create context for this conversation
            DocumentContext.objects.create(
                conversation=conversation,
                context_data={}
            )
            
            return JsonResponse({
                'success': True,
                'conversation': {
                    'id': str(conversation.id),
                    'title': conversation.title,
                    'is_active': conversation.is_active,
                    'message_count': 0,
                    'last_activity': conversation.last_activity.isoformat()
                }
            })
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return JsonResponse({'error': 'Session not found'}, status=404)
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def delete_conversation(request, conversation_id):
        """Delete a conversation"""
        try:
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            # Get the conversation to delete
            conversation = Conversation.objects.get(
                id=conversation_id,
                session=doc_session
            )
            
            # Check if this is the last conversation
            total_conversations = doc_session.conversations.count()
            if total_conversations <= 1:
                return JsonResponse({
                    'error': 'Cannot delete the last conversation'
                }, status=400)
            
            was_active = conversation.is_active
            
            # Delete associated artifacts and documents
            for message in conversation.messages.all():
                message.generated_artifacts.all().delete()
            
            # Delete documents associated with this conversation
            conversation.documents.all().delete()
            
            # Delete the conversation (this will cascade delete messages and context)
            conversation.delete()
            
            # If we deleted the active conversation, activate another one
            if was_active:
                new_active = doc_session.conversations.filter(is_active=True).first()
                if new_active:
                    new_active.is_active = True
                    new_active.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Conversation deleted successfully'
            })
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return JsonResponse({'error': 'Session not found'}, status=404)
        except Conversation.DoesNotExist:
            return JsonResponse({'error': 'Conversation not found'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting conversation: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def rename_conversation(request, conversation_id):
        """Rename a conversation"""
        try:
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            # Get the conversation to rename
            conversation = Conversation.objects.get(
                id=conversation_id,
                session=doc_session
            )
            
            # Get new title
            new_title = request.POST.get('title', '').strip()
            if not new_title:
                return JsonResponse({'error': 'Title cannot be empty'}, status=400)
            
            conversation.title = new_title
            conversation.save()
            
            return JsonResponse({
                'success': True,
                'conversation': {
                    'id': str(conversation.id),
                    'title': conversation.title
                }
            })
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return JsonResponse({'error': 'Session not found'}, status=404)
        except Conversation.DoesNotExist:
            return JsonResponse({'error': 'Conversation not found'}, status=404)
        except Exception as e:
            logger.error(f"Error renaming conversation: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @require_http_methods(["POST"])
    def switch_conversation(request, conversation_id):
        """Switch to a different conversation"""
        try:
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            # Get the conversation to switch to
            conversation = Conversation.objects.get(
                id=conversation_id,
                session=doc_session
            )
            
            # Deactivate all conversations for this session
            Conversation.objects.filter(session=doc_session).update(is_active=False)
            
            # Activate the target conversation
            conversation.is_active = True
            conversation.update_activity()
            conversation.save()
            
            return JsonResponse({
                'success': True,
                'redirect_url': '/'  # Redirect to main chat page to reload with new conversation
            })
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return JsonResponse({'error': 'Session not found'}, status=404)
        except Conversation.DoesNotExist:
            return JsonResponse({'error': 'Conversation not found'}, status=404)
        except Exception as e:
            logger.error(f"Error switching conversation: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    @require_http_methods(["GET"])
    def list_conversations(request):
        """Get list of conversations for current session"""
        try:
            session_key = request.session.session_key
            if not session_key:
                return render(request, 'chat/partials/conversation_list_empty.html')
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            conversations = doc_session.conversations.all().order_by('-last_activity')
            active_conversation = conversations.first()
            
            context = {
                'conversations': conversations,
                'active_conversation': active_conversation
            }
            
            return render(request, 'chat/partials/conversation_list_items.html', context)
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return render(request, 'chat/partials/conversation_list_empty.html')
        except Exception as e:
            logger.error(f"Error listing conversations: {str(e)}")
            return render(request, 'chat/partials/conversation_list_empty.html')
    
    @staticmethod
    @require_http_methods(["GET"])
    def list_conversations_json(request):
        """Get list of conversations as JSON for API calls"""
        try:
            session_key = request.session.session_key
            if not session_key:
                return JsonResponse({'error': 'No active session'}, status=400)
            
            session_obj = Session.objects.get(session_key=session_key)
            doc_session = DocumentSession.objects.get(session=session_obj)
            
            conversations = doc_session.conversations.all().order_by('-last_activity')
            
            conversation_list = []
            for conv in conversations:
                conversation_list.append({
                    'id': str(conv.id),
                    'title': conv.title,
                    'is_active': conv.is_active,
                    'message_count': conv.messages.count(),
                    'document_count': conv.documents.count(),
                    'last_message_preview': conv.get_last_message_preview(),
                    'last_activity': conv.last_activity.isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'conversations': conversation_list
            })
            
        except (Session.DoesNotExist, DocumentSession.DoesNotExist):
            return JsonResponse({'error': 'Session not found'}, status=404)
        except Exception as e:
            logger.error(f"Error listing conversations: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)