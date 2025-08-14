from django.http import FileResponse, HttpResponse, Http404
from django.core.files.storage import default_storage
from django.conf import settings
from django.utils.encoding import smart_str
from apps.chat.models import Artifact
from pathlib import Path
import mimetypes
import logging
import os

logger = logging.getLogger(__name__)

class ArtifactDownloader:
    """Handle secure artifact downloads with proper headers and validation"""
    
    def download_artifact(self, artifact: Artifact, inline: bool = False) -> FileResponse:
        """
        Download artifact file with security checks
        
        Args:
            artifact: Artifact model instance
            inline: If True, serve images inline instead of as download
            
        Returns:
            FileResponse with proper headers
        """
        try:
            file_path = Path(artifact.file_path)
            
            # Security check: ensure file exists and is readable
            if not file_path.exists():
                logger.warning(f"Artifact file not found: {artifact.file_path}")
                raise Http404("File not found")
            
            # Ensure file is within allowed directories
            if not self._is_safe_path(file_path):
                logger.warning(f"Unsafe file path attempted: {artifact.file_path}")
                raise Http404("File not accessible")
            
            # Get MIME type
            content_type = self._get_content_type(artifact.file_type, file_path)
            
            # Open file for response
            try:
                file_handle = open(file_path, 'rb')
            except (IOError, OSError) as e:
                logger.error(f"Error opening file {artifact.file_path}: {str(e)}")
                raise Http404("File not accessible")
            
            # Create response with proper headers
            response = FileResponse(
                file_handle,
                content_type=content_type,
                filename=artifact.file_name
            )
            
            # Set additional headers
            response['Content-Length'] = artifact.file_size
            
            # Set Content-Disposition based on file type and inline parameter
            if inline and content_type.startswith('image/'):
                # Serve images inline for display in chat
                response['Content-Disposition'] = f'inline; filename="{smart_str(artifact.file_name)}"'
            else:
                # Force download for other files or when explicitly requested
                response['Content-Disposition'] = f'attachment; filename="{smart_str(artifact.file_name)}"'
            
            # Cache control for generated artifacts
            response['Cache-Control'] = 'private, max-age=3600'  # 1 hour cache
            
            logger.info(f"Serving artifact {'inline' if inline else 'download'}: {artifact.file_name} ({artifact.file_size} bytes)")
            
            return response
            
        except Exception as e:
            logger.error(f"Error downloading artifact {artifact.id}: {str(e)}")
            raise Http404("Download failed")
    
    def _is_safe_path(self, file_path: Path) -> bool:
        """Check if file path is within allowed directories"""
        try:
            # Resolve path to prevent directory traversal
            resolved_path = file_path.resolve()
            
            # Check against allowed base paths
            allowed_paths = [
                # Project temp directories
                Path.cwd() / 'temp',  # Main temp directory
                Path.cwd() / 'media',  # Media directory
                # Settings-based paths
                getattr(settings, 'TEMP_FILE_ROOT', Path.cwd() / 'temp'),
                Path('/tmp/ultra_pdf_chatbot'),  # Unix temp directory
            ]
            
            for allowed_path in allowed_paths:
                try:
                    # Resolve and check if file is within allowed path
                    resolved_allowed = Path(allowed_path).resolve()
                    resolved_path.relative_to(resolved_allowed)
                    return True
                except (ValueError, OSError):
                    continue
            
            return False
            
        except (OSError, ValueError):
            return False
    
    def _get_content_type(self, stored_type: str, file_path: Path) -> str:
        """Determine content type for file"""
        # Use stored type if available and valid
        if stored_type and stored_type != 'application/octet-stream':
            return stored_type
        
        # Guess from file extension
        guessed_type, _ = mimetypes.guess_type(str(file_path))
        if guessed_type:
            return guessed_type
        
        # Extension-based mapping for common types
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
            '.html': 'text/html',
            '.zip': 'application/zip'
        }
        
        return type_mapping.get(ext, 'application/octet-stream')


class SecureFileDownloader:
    """Generic secure file downloader for various file types"""
    
    @staticmethod
    def download_file(file_path: str, filename: str = None, content_type: str = None) -> FileResponse:
        """
        Download any file with security checks
        
        Args:
            file_path: Path to file
            filename: Download filename (optional)
            content_type: MIME type (optional)
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise Http404("File not found")
            
            # Security check
            downloader = ArtifactDownloader()
            if not downloader._is_safe_path(path):
                raise Http404("File not accessible")
            
            # Determine filename
            if not filename:
                filename = path.name
            
            # Determine content type
            if not content_type:
                content_type = downloader._get_content_type('', path)
            
            # Open and serve file
            file_handle = open(path, 'rb')
            response = FileResponse(
                file_handle,
                content_type=content_type,
                filename=filename
            )
            
            response['Content-Length'] = path.stat().st_size
            response['Content-Disposition'] = f'attachment; filename="{smart_str(filename)}"'
            
            return response
            
        except Exception as e:
            logger.error(f"Error downloading file {file_path}: {str(e)}")
            raise Http404("Download failed")


class ChartDownloader:
    """Specialized downloader for chart images"""
    
    @staticmethod
    def download_chart(chart_path: str, chart_name: str = None) -> FileResponse:
        """Download chart image"""
        if not chart_name:
            chart_name = f"chart_{Path(chart_path).stem}.png"
        
        return SecureFileDownloader.download_file(
            file_path=chart_path,
            filename=chart_name,
            content_type='image/png'
        )


class DocumentDownloader:
    """Specialized downloader for processed documents"""
    
    @staticmethod
    def download_modified_document(doc_path: str, original_name: str) -> FileResponse:
        """Download modified document"""
        path = Path(doc_path)
        ext = path.suffix.lower()
        
        # Determine content type based on extension
        content_types = {
            '.pdf': 'application/pdf',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        
        content_type = content_types.get(ext, 'application/octet-stream')
        
        # Generate filename with "modified_" prefix
        base_name = Path(original_name).stem
        original_ext = Path(original_name).suffix
        filename = f"modified_{base_name}{original_ext}"
        
        return SecureFileDownloader.download_file(
            file_path=doc_path,
            filename=filename,
            content_type=content_type
        )


class BulkDownloader:
    """Handle bulk downloads and zip archives"""
    
    @staticmethod
    def create_zip_download(file_paths: list, zip_name: str = "download.zip") -> FileResponse:
        """
        Create zip archive of multiple files
        
        Args:
            file_paths: List of (file_path, filename_in_zip) tuples
            zip_name: Name of zip file
        """
        import zipfile
        import tempfile
        
        try:
            # Create temporary zip file
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path, archive_name in file_paths:
                    path = Path(file_path)
                    if path.exists():
                        # Security check
                        downloader = ArtifactDownloader()
                        if downloader._is_safe_path(path):
                            zip_file.write(path, archive_name)
                        else:
                            logger.warning(f"Skipped unsafe path in zip: {file_path}")
                    else:
                        logger.warning(f"File not found for zip: {file_path}")
            
            # Serve zip file
            zip_file_handle = open(temp_zip.name, 'rb')
            response = FileResponse(
                zip_file_handle,
                content_type='application/zip',
                filename=zip_name
            )
            
            response['Content-Length'] = Path(temp_zip.name).stat().st_size
            response['Content-Disposition'] = f'attachment; filename="{smart_str(zip_name)}"'
            
            # Clean up temp file after response
            def cleanup():
                try:
                    os.unlink(temp_zip.name)
                except OSError:
                    pass
            
            response._closable_objects.append(cleanup)
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating zip download: {str(e)}")
            raise Http404("Zip creation failed")


# Utility functions for common download scenarios

def download_artifact_by_id(artifact_id: str) -> FileResponse:
    """Download artifact by ID"""
    try:
        artifact = Artifact.objects.get(id=artifact_id)
        downloader = ArtifactDownloader()
        return downloader.download_artifact(artifact)
    except Artifact.DoesNotExist:
        raise Http404("Artifact not found")


def download_session_artifacts(session_id: str) -> FileResponse:
    """Download all artifacts from a session as zip"""
    from apps.chat.models import Conversation, Message
    from apps.documents.models import DocumentSession
    from django.contrib.sessions.models import Session
    
    try:
        # Get session artifacts
        session_obj = Session.objects.get(session_key=session_id)
        doc_session = DocumentSession.objects.get(session=session_obj)
        conversations = Conversation.objects.filter(session=doc_session)
        messages = Message.objects.filter(conversation__in=conversations)
        artifacts = Artifact.objects.filter(message__in=messages)
        
        if not artifacts.exists():
            raise Http404("No artifacts found")
        
        # Prepare file list for zip
        file_paths = []
        for artifact in artifacts:
            if Path(artifact.file_path).exists():
                file_paths.append((artifact.file_path, artifact.file_name))
        
        if not file_paths:
            raise Http404("No downloadable files found")
        
        # Create zip
        zip_name = f"session_artifacts_{session_id[:8]}.zip"
        return BulkDownloader.create_zip_download(file_paths, zip_name)
        
    except (Session.DoesNotExist, DocumentSession.DoesNotExist):
        raise Http404("Session not found")