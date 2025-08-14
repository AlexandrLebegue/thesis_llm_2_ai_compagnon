from celery import shared_task
from django.utils import timezone
from apps.agents.orchestrator import ChatbotOrchestrator
from apps.chat.models import Message, Artifact
from apps.documents.models import DocumentContext
import logging
from typing import Dict, Any, Optional
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2)
def run_agent_task_async(
    self,
    instruction: str,
    context: Dict[str, Any],
    session_id: str,
    message_id: str
):
    """
    Run SmolAgents orchestrator asynchronously
    
    Args:
        instruction: User instruction/request
        context: Document context data
        session_id: Session identifier
        message_id: Message ID to update with results
    
    Returns:
        dict: Agent execution result with artifacts
    """
    try:
        logger.info(f"Starting agent task for message {message_id}")
        
        # Get message object
        try:
            message = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            error_msg = f"Message {message_id} not found"
            logger.error(error_msg)
            return {'status': 'error', 'error': error_msg}
        
        # Update message status
        message.task_status = 'PROCESSING'
        message.content = 'Processing your request with AI agents...'
        message.save()
        
        try:
            # Initialize orchestrator with session context
            orchestrator = ChatbotOrchestrator(session_id=session_id)
            
            # Process request with message object (orchestrator will handle artifact creation)
            result = orchestrator.process_request(
                instruction=instruction,
                context=context,
                session_id=session_id,
                message=message
            )
            
            if result['status'] == 'error':
                message.task_status = 'FAILURE'
                message.content = f"Error: {result.get('error', 'Unknown error occurred')}"
                message.save()
                return result
            
            # Update message with results (artifacts already created by orchestrator)
            message.task_status = 'SUCCESS'
            message.content = result.get('result', 'Task completed successfully.')
            message.artifacts = result.get('artifacts', [])
            message.save()
            
            logger.info(f"Successfully completed agent task for message {message_id}")
            
            return {
                'status': 'success',
                'result': message.content,
                'artifacts': result.get('artifacts', []),
                'message_id': message_id
            }
            
        except Exception as e:
            error_msg = f"Error running agent task for message {message_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            message.task_status = 'FAILURE'
            message.content = f"Error: {str(e)}"
            message.save()
            
            # Retry logic
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying agent task for message {message_id} (attempt {self.request.retries + 1})")
                raise self.retry(countdown=30 * (2 ** self.request.retries))
            
            return {'status': 'error', 'error': error_msg}
    
    except Exception as e:
        error_msg = f"Fatal error in agent task for message {message_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {'status': 'error', 'error': error_msg}


def _process_artifact(artifact_data: Dict[str, Any], message: Message, session_id: str) -> Optional[Dict[str, Any]]:
    """Process artifact from agent result"""
    try:
        artifact_path = artifact_data.get('path')
        if not artifact_path or not Path(artifact_path).exists():
            logger.warning(f"Artifact path not found: {artifact_path}")
            return None
        
        file_path = Path(artifact_path)
        file_size = file_path.stat().st_size
        
        # Determine file type
        file_type = _get_file_type(file_path)
        
        # Generate unique ID for artifact
        artifact_id = str(uuid.uuid4())
        
        return {
            'id': artifact_id,
            'name': artifact_data.get('name', file_path.name),
            'path': str(artifact_path),
            'type': file_type,
            'size': file_size,
            'created_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing artifact: {str(e)}")
        return None


def _get_file_type(file_path: Path) -> str:
    """Determine MIME type from file extension"""
    ext = file_path.suffix.lower()
    
    type_mapping = {
        '.pdf': 'application/pdf',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.svg': 'image/svg+xml',
        '.csv': 'text/csv',
        '.txt': 'text/plain',
        '.json': 'application/json',
        '.html': 'text/html'
    }
    
    return type_mapping.get(ext, 'application/octet-stream')


@shared_task(bind=True, max_retries=2)
def process_complex_request(
    self,
    instruction: str,
    context: Dict[str, Any],
    session_id: str,
    message_id: str,
    complexity_level: str = 'high'
):
    """
    Process complex requests that require extended processing time
    
    Args:
        instruction: User instruction
        context: Document context
        session_id: Session ID
        message_id: Message ID
        complexity_level: 'high', 'medium', 'low'
    """
    try:
        logger.info(f"Starting complex request processing for message {message_id} (level: {complexity_level})")
        
        # Get message
        message = Message.objects.get(id=message_id)
        message.task_status = 'PROCESSING'
        message.content = f'Processing complex request ({complexity_level} complexity)...'
        message.save()
        
        # Set processing parameters based on complexity
        if complexity_level == 'high':
            max_steps = 15
            timeout = 300  # 5 minutes
        elif complexity_level == 'medium':
            max_steps = 10
            timeout = 180  # 3 minutes
        else:
            max_steps = 5
            timeout = 60   # 1 minute
        
        # Initialize orchestrator with extended parameters
        orchestrator = ChatbotOrchestrator(session_id=session_id)
        orchestrator.agent.max_steps = max_steps
        
        # Process with progress updates
        message.content = 'Analyzing request and planning execution...'
        message.save()
        
        result = orchestrator.process_request(
            instruction=instruction,
            context=context,
            session_id=session_id,
            message=message
        )
        
        if result['status'] == 'error':
            message.task_status = 'FAILURE'
            message.content = f"Error: {result.get('error', 'Processing failed')}"
            message.save()
            return result
        
        # Update message (artifacts already created by orchestrator)
        message.task_status = 'SUCCESS'
        message.content = result.get('result', 'Complex processing completed.')
        message.artifacts = result.get('artifacts', [])
        message.save()
        
        logger.info(f"Complex request completed for message {message_id}")
        
        return {
            'status': 'success',
            'result': message.content,
            'artifacts': result.get('artifacts', []),
            'complexity_level': complexity_level
        }
        
    except Exception as e:
        error_msg = f"Error in complex request processing: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        message = Message.objects.get(id=message_id)
        message.task_status = 'FAILURE'
        message.content = f"Error: {str(e)}"
        message.save()
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)
        
        return {'status': 'error', 'error': error_msg}


@shared_task
def cleanup_expired_artifacts():
    """Clean up expired artifacts"""
    try:
        expired_artifacts = Artifact.objects.filter(
            expires_at__lt=timezone.now()
        )
        
        deleted_count = 0
        for artifact in expired_artifacts:
            try:
                # Delete file
                file_path = Path(artifact.file_path)
                if file_path.exists():
                    file_path.unlink()
                
                # Delete database record
                artifact.delete()
                deleted_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to delete artifact {artifact.id}: {str(e)}")
        
        logger.info(f"Cleaned up {deleted_count} expired artifacts")
        
        return {
            'status': 'success',
            'deleted_count': deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up artifacts: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def batch_agent_processing(instruction_batch: list, context: Dict[str, Any], session_id: str):
    """Process multiple agent requests in batch"""
    results = []
    
    for i, instruction in enumerate(instruction_batch):
        try:
            # Create temporary message for tracking
            from apps.chat.models import Conversation
            from apps.documents.models import DocumentSession
            from django.contrib.sessions.models import Session
            
            session_obj = Session.objects.get(session_key=session_id)
            doc_session = DocumentSession.objects.get(session=session_obj)
            conversation = Conversation.objects.filter(session=doc_session).first()
            
            if not conversation:
                conversation = Conversation.objects.create(session=doc_session)
            
            message = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=f'Processing batch item {i+1}...',
                task_status='PENDING'
            )
            
            # Queue individual task
            task = run_agent_task_async.delay(
                instruction=instruction,
                context=context,
                session_id=session_id,
                message_id=str(message.id)
            )
            
            results.append({
                'index': i,
                'instruction': instruction[:100] + '...' if len(instruction) > 100 else instruction,
                'message_id': str(message.id),
                'task_id': task.id,
                'status': 'queued'
            })
            
        except Exception as e:
            logger.error(f"Failed to queue batch item {i}: {str(e)}")
            results.append({
                'index': i,
                'instruction': instruction[:100] + '...' if len(instruction) > 100 else instruction,
                'status': 'error',
                'error': str(e)
            })
    
    return {
        'status': 'success',
        'batch_size': len(instruction_batch),
        'results': results
    }


@shared_task
def analyze_session_activity(session_id: str):
    """Analyze session activity and provide insights"""
    try:
        from apps.documents.session_manager import SessionManager
        from apps.chat.models import Conversation, Message
        from django.contrib.sessions.models import Session
        from django.db.models import Count, Avg
        
        # Get session data
        session_manager = SessionManager(session_id)
        session_info = session_manager.get_session_info()
        
        # Get conversation data
        session_obj = Session.objects.get(session_key=session_id)
        doc_session = session_manager.doc_session
        conversations = Conversation.objects.filter(session=doc_session)
        
        # Calculate statistics
        total_messages = Message.objects.filter(conversation__in=conversations).count()
        user_messages = Message.objects.filter(
            conversation__in=conversations,
            role='user'
        ).count()
        assistant_messages = Message.objects.filter(
            conversation__in=conversations,
            role='assistant'
        ).count()
        
        # Task statistics
        task_messages = Message.objects.filter(
            conversation__in=conversations,
            task_id__isnull=False
        )
        successful_tasks = task_messages.filter(task_status='SUCCESS').count()
        failed_tasks = task_messages.filter(task_status='FAILURE').count()
        
        # Generate insights
        insights = {
            'session_id': session_id,
            'analysis_timestamp': timezone.now().isoformat(),
            'document_stats': session_info,
            'conversation_stats': {
                'total_messages': total_messages,
                'user_messages': user_messages,
                'assistant_messages': assistant_messages,
                'conversation_count': conversations.count()
            },
            'task_stats': {
                'total_tasks': task_messages.count(),
                'successful_tasks': successful_tasks,
                'failed_tasks': failed_tasks,
                'success_rate': round(successful_tasks / max(task_messages.count(), 1) * 100, 1)
            },
            'recommendations': _generate_recommendations(session_info, total_messages, successful_tasks, failed_tasks)
        }
        
        logger.info(f"Generated activity analysis for session {session_id}")
        return {'status': 'success', 'insights': insights}
        
    except Exception as e:
        logger.error(f"Error analyzing session activity: {str(e)}")
        return {'status': 'error', 'error': str(e)}


def _generate_recommendations(session_info: Dict, total_messages: int, successful_tasks: int, failed_tasks: int) -> list:
    """Generate recommendations based on session analysis"""
    recommendations = []
    
    # Document recommendations
    if session_info['document_count'] == 0:
        recommendations.append("Consider uploading documents to enhance AI capabilities")
    elif session_info['document_count'] > 15:
        recommendations.append("Large number of documents - consider organizing or removing unused ones")
    
    # Task performance recommendations
    if failed_tasks > successful_tasks:
        recommendations.append("High task failure rate - try simpler requests or check document quality")
    elif successful_tasks > 10:
        recommendations.append("Great task success rate! You're making good use of the AI capabilities")
    
    # Usage recommendations
    if total_messages > 50:
        recommendations.append("Very active session - consider starting fresh if performance degrades")
    elif total_messages < 5:
        recommendations.append("New session - explore different AI capabilities with your documents")
    
    return recommendations