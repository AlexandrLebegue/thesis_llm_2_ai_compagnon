import uuid
from django.db import models
from django.contrib.sessions.models import Session
from django.core.validators import FileExtensionValidator
from django.conf import settings


class DocumentSession(models.Model):
    """Links documents to a browser session"""
    session = models.OneToOneField(Session, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    document_count = models.IntegerField(default=0)
    total_size = models.BigIntegerField(default=0)  # bytes
    
    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"DocumentSession {self.session.session_key} ({self.document_count} docs)"
    
    @property
    def documents(self):
        """Get all documents across all conversations in this session"""
        from apps.documents.models import Document
        return Document.objects.filter(conversation__session=self)


class Document(models.Model):
    """Uploaded document model"""
    DOCUMENT_TYPES = [
        ('pdf', 'PDF Document'),
        ('xlsx', 'Excel Spreadsheet'),
        ('docx', 'Word Document'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey('chat.Conversation', on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    original_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)  # Stored in temp directory
    document_type = models.CharField(max_length=10, choices=DOCUMENT_TYPES)
    file_size = models.BigIntegerField()  # bytes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Extracted content
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)  # Store extracted metadata
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['conversation', 'status']),
            models.Index(fields=['uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.original_name} ({self.get_status_display()})"


class DocumentContext(models.Model):
    """Aggregated context from all documents in a conversation"""
    conversation = models.OneToOneField('chat.Conversation', on_delete=models.CASCADE, null=True, blank=True)
    context_data = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)
    
    def update_context(self):
        """Rebuild context from all ready documents in this conversation"""
        documents = self.conversation.documents.filter(status='ready')
        context = {
            'document_count': documents.count(),
            'documents': []
        }
        
        for doc in documents:
            context['documents'].append({
                'id': str(doc.id),
                'name': doc.original_name,
                'type': doc.document_type,
                'summary': doc.summary,
                'metadata': doc.metadata
            })
        
        self.context_data = context
        self.save()
    
    def __str__(self):
        return f"Context for {self.conversation}"