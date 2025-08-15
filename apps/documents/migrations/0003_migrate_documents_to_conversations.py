# Generated data migration for multi-conversation system

from django.db import migrations


def migrate_documents_to_conversations(apps, schema_editor):
    """
    Migrate existing documents and contexts to conversations.
    For each DocumentSession, create a default conversation and move all documents there.
    """
    DocumentSession = apps.get_model('documents', 'DocumentSession')
    Document = apps.get_model('documents', 'Document')
    DocumentContext = apps.get_model('documents', 'DocumentContext')
    Conversation = apps.get_model('chat', 'Conversation')
    
    db_alias = schema_editor.connection.alias
    
    # First, handle conversations for each document session
    for doc_session in DocumentSession.objects.using(db_alias).all():
        # Get or create a default conversation for this session
        conversation, created = Conversation.objects.using(db_alias).get_or_create(
            session=doc_session,
            defaults={
                'title': 'Main Conversation',
                'is_active': True
            }
        )
        
        # Move all documents without conversation to this conversation
        Document.objects.using(db_alias).filter(
            conversation__isnull=True
        ).update(conversation=conversation)
        
        # Handle DocumentContext - since it's OneToOne, we need to be careful
        # Check if this conversation already has a context
        existing_context = DocumentContext.objects.using(db_alias).filter(
            conversation=conversation
        ).first()
        
        if not existing_context:
            # Try to get the first orphaned context and assign it to this conversation
            orphaned_context = DocumentContext.objects.using(db_alias).filter(
                conversation__isnull=True
            ).first()
            
            if orphaned_context:
                orphaned_context.conversation = conversation
                orphaned_context.save(using=db_alias)
            else:
                # Create new context if no orphaned one exists
                DocumentContext.objects.using(db_alias).create(
                    conversation=conversation,
                    context_data={}
                )
    
    # Clean up any remaining orphaned DocumentContext objects
    DocumentContext.objects.using(db_alias).filter(
        conversation__isnull=True
    ).delete()


def reverse_migrate_conversations_to_documents(apps, schema_editor):
    """
    Reverse migration - move documents and contexts back to sessions.
    This would require restoring the session field which is complex.
    """
    # Since the session field has been removed, we can't easily reverse this
    # This is expected for this type of structural change
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_remove_document_documents_d_session_78c1f6_idx_and_more'),
        ('chat', '0003_conversation_is_active_conversation_title_and_more'),
    ]

    operations = [
        migrations.RunPython(
            migrate_documents_to_conversations,
            reverse_migrate_conversations_to_documents,
        ),
    ]