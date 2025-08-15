from django.urls import path
from .views import ChatView
# Conditional import for downloads
try:
    from .downloads import download_session_artifacts
    DOWNLOADS_AVAILABLE = True
except ImportError:
    DOWNLOADS_AVAILABLE = False
    def download_session_artifacts(request, session_id):
        from django.http import HttpResponse
        return HttpResponse('Downloads not available in development mode', status=503)

app_name = 'chat'

urlpatterns = [
    # Main chat interface
    path('', ChatView.index, name='index'),
    
    # Chat message handling
    path('send/', ChatView.send_message, name='send_message'),
    path('clear/', ChatView.clear_chat, name='clear_chat'),
    
    # Conversation management
    path('conversations/', ChatView.list_conversations, name='list_conversations'),
    path('conversations/json/', ChatView.list_conversations_json, name='list_conversations_json'),
    path('conversations/create/', ChatView.create_conversation, name='create_conversation'),
    path('conversations/<uuid:conversation_id>/delete/', ChatView.delete_conversation, name='delete_conversation'),
    path('conversations/<uuid:conversation_id>/rename/', ChatView.rename_conversation, name='rename_conversation'),
    path('conversations/<uuid:conversation_id>/switch/', ChatView.switch_conversation, name='switch_conversation'),
    
    # Task status checking for async operations
    path('task/<str:task_id>/status/', ChatView.check_task_status, name='check_task_status'),
    
    # Artifact downloads and inline display
    path('download/<uuid:artifact_id>/', ChatView.download_artifact, name='download_artifact'),
    path('view/<uuid:artifact_id>/', ChatView.view_artifact_inline, name='view_artifact_inline'),
    path('preview/word/<uuid:artifact_id>/', ChatView.view_word_preview, name='view_word_preview'),
    path('preview/excel/<uuid:artifact_id>/', ChatView.view_excel_preview, name='view_excel_preview'),
    path('download/session/<str:session_id>/artifacts/', download_session_artifacts, name='download_session_artifacts'),
]