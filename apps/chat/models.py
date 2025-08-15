import uuid
from django.db import models
from apps.documents.models import DocumentSession


class Conversation(models.Model):
    """Chat conversation linked to document session"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(DocumentSession, on_delete=models.CASCADE, related_name='conversations')
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"Conversation {self.id} (started {self.started_at.strftime('%Y-%m-%d %H:%M')})"


class Message(models.Model):
    """Individual chat message"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For tracking async tasks
    task_id = models.CharField(max_length=255, blank=True)
    task_status = models.CharField(max_length=50, blank=True)
    
    # Attachments/results
    artifacts = models.JSONField(default=list)  # List of generated file IDs
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['task_id']),
        ]
    
    def __str__(self):
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.get_role_display()}: {content_preview}"


class Artifact(models.Model):
    """Generated files from agent operations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='generated_artifacts')
    file_path = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # MIME type
    file_size = models.BigIntegerField()
    preview_html = models.TextField(blank=True, null=True)  # HTML preview for Word docs
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.file_name} ({self.file_type})"