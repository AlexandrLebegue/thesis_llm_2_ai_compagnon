from django.contrib import admin
from .models import Conversation, Message, Artifact


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id_short', 'session_key', 'started_at', 'last_activity', 'message_count']
    list_filter = ['started_at', 'last_activity']
    search_fields = ['id', 'session__session__session_key']
    readonly_fields = ['id', 'started_at', 'last_activity']
    ordering = ['-last_activity']
    
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'
    
    def session_key(self, obj):
        session_key = obj.session.session.session_key
        return session_key[:10] + '...' if len(session_key) > 10 else session_key
    session_key.short_description = 'Session'
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


class ArtifactInline(admin.TabularInline):
    model = Artifact
    extra = 0
    readonly_fields = ['id', 'created_at', 'file_size_mb']
    fields = ['file_name', 'file_type', 'file_size_mb', 'expires_at']
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024 * 1024):.2f} MB" if obj.file_size else "0 MB"
    file_size_mb.short_description = 'Size'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id_short', 'conversation_id_short', 'role', 'content_preview', 'created_at', 'has_task']
    list_filter = ['role', 'created_at', 'task_status']
    search_fields = ['content', 'conversation__id', 'task_id']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
    inlines = [ArtifactInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation', 'role', 'created_at')
        }),
        ('Content', {
            'fields': ('content',),
            'classes': ('wide',)
        }),
        ('Task Information', {
            'fields': ('task_id', 'task_status'),
            'classes': ('collapse',)
        }),
        ('Artifacts', {
            'fields': ('artifacts',),
            'classes': ('collapse',)
        }),
    )
    
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'
    
    def conversation_id_short(self, obj):
        return str(obj.conversation.id)[:8] + '...'
    conversation_id_short.short_description = 'Conversation'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
    
    def has_task(self, obj):
        return bool(obj.task_id)
    has_task.short_description = 'Has Task'
    has_task.boolean = True


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ['id_short', 'file_name', 'file_type', 'file_size_mb', 'created_at', 'expires_at', 'is_expired']
    list_filter = ['file_type', 'created_at', 'expires_at']
    search_fields = ['file_name', 'message__content']
    readonly_fields = ['id', 'created_at', 'file_size_mb']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'message', 'file_name', 'file_type')
        }),
        ('File Details', {
            'fields': ('file_path', 'file_size_mb', 'created_at', 'expires_at')
        }),
    )
    
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'ID'
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024 * 1024):.2f} MB"
    file_size_mb.short_description = 'File Size'
    
    def is_expired(self, obj):
        from django.utils import timezone
        return obj.expires_at < timezone.now()
    is_expired.short_description = 'Expired'
    is_expired.boolean = True