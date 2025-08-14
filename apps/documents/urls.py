from django.urls import path
from .views import DocumentView

app_name = 'documents'

urlpatterns = [
    # Document upload
    path('upload/', DocumentView.upload_document, name='upload_document'),
    
    # Document management
    path('<uuid:document_id>/status/', DocumentView.document_status, name='document_status'),
    path('<uuid:document_id>/delete/', DocumentView.delete_document, name='delete_document'),
    path('<uuid:document_id>/download/', DocumentView.download_document, name='download_document'),
    path('<uuid:document_id>/regenerate-summary/', DocumentView.regenerate_summary, name='regenerate_summary'),
    
    # Session document listing
    path('list/', DocumentView.list_documents, name='list_documents'),
    
    # Session management endpoints
    path('session/info/', DocumentView.session_info, name='session_info'),
    path('session/cleanup/', DocumentView.cleanup_session, name='cleanup_session'),
]