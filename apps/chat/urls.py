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
    
    # Task status checking for async operations
    path('task/<str:task_id>/status/', ChatView.check_task_status, name='check_task_status'),
    
    # Artifact downloads and inline display
    path('download/<uuid:artifact_id>/', ChatView.download_artifact, name='download_artifact'),
    path('view/<uuid:artifact_id>/', ChatView.view_artifact_inline, name='view_artifact_inline'),
    path('download/session/<str:session_id>/artifacts/', download_session_artifacts, name='download_session_artifacts'),
]