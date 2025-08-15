from django.contrib import admin
from .models import DocumentSession, Document, DocumentContext


@admin.register(DocumentSession)
class DocumentSessionAdmin(admin.ModelAdmin):
    list_display = ['session_key', 'created_at', 'document_count', 'total_size_mb']
    list_filter = ['created_at']
    search_fields = ['session__session_key']
    readonly_fields = ['session', 'created_at']
    ordering = ['-created_at']
    
    def session_key(self, obj):
        return obj.session.session_key[:10] + '...' if len(obj.session.session_key) > 10 else obj.session.session_key
    session_key.short_description = 'Session Key'
    
    def total_size_mb(self, obj):
        return f"{obj.total_size / (1024 * 1024):.2f} MB"
    total_size_mb.short_description = 'Total Size'


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['original_name', 'document_type', 'status', 'file_size_mb', 'uploaded_at']
    list_filter = ['document_type', 'status', 'uploaded_at']
    search_fields = ['original_name', 'conversation__session__session__session_key']
    readonly_fields = ['id', 'uploaded_at', 'processed_at']
    list_editable = ['status']
    ordering = ['-uploaded_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'original_name', 'document_type', 'status')
        }),
        ('File Details', {
            'fields': ('file_path', 'file_size', 'uploaded_at', 'processed_at')
        }),
        ('Content', {
            'fields': ('summary', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024 * 1024):.2f} MB"
    file_size_mb.short_description = 'File Size'


@admin.register(DocumentContext)
class DocumentContextAdmin(admin.ModelAdmin):
    list_display = ['conversation_title', 'document_count', 'last_updated']
    readonly_fields = ['conversation', 'last_updated']
    ordering = ['-last_updated']
    
    fieldsets = (
        ('Conversation Information', {
            'fields': ('conversation', 'last_updated')
        }),
        ('Context Data', {
            'fields': ('context_data',),
            'classes': ('wide',)
        }),
    )
    
    def conversation_title(self, obj):
        return obj.conversation.title
    conversation_title.short_description = 'Conversation'
    
    def document_count(self, obj):
        return obj.context_data.get('document_count', 0)
    document_count.short_description = 'Document Count'