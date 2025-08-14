from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.deconstruct import deconstructible
from pathlib import Path
import os
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)

@deconstructible
class SessionFileStorage(Storage):
    """Custom storage backend for session-based file management"""
    
    def __init__(self, session_id: str, base_path: Optional[Path] = None):
        self.session_id = session_id
        self.base_path = base_path or settings.TEMP_FILE_ROOT / session_id
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _open(self, name: str, mode: str = 'rb'):
        """Open a file from storage"""
        full_path = self.base_path / name
        try:
            return open(full_path, mode)
        except FileNotFoundError:
            raise FileNotFoundError(f"File {name} not found in session storage")
    
    def _save(self, name: str, content) -> str:
        """Save content to storage"""
        # Generate unique filename if needed
        if self.exists(name):
            base, ext = os.path.splitext(name)
            name = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
        
        full_path = self.base_path / name
        
        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        with open(full_path, 'wb') as f:
            if hasattr(content, 'chunks'):
                # Django UploadedFile
                for chunk in content.chunks():
                    f.write(chunk)
            elif hasattr(content, 'read'):
                # File-like object
                f.write(content.read())
            else:
                # Bytes or string
                if isinstance(content, str):
                    content = content.encode('utf-8')
                f.write(content)
        
        logger.info(f"Saved file {name} to session {self.session_id}")
        return name
    
    def exists(self, name: str) -> bool:
        """Check if file exists in storage"""
        full_path = self.base_path / name
        return full_path.exists()
    
    def delete(self, name: str) -> bool:
        """Delete file from storage"""
        full_path = self.base_path / name
        try:
            if full_path.exists():
                full_path.unlink()
                logger.info(f"Deleted file {name} from session {self.session_id}")
                return True
        except Exception as e:
            logger.error(f"Error deleting file {name}: {str(e)}")
        return False
    
    def size(self, name: str) -> int:
        """Get file size"""
        full_path = self.base_path / name
        try:
            return full_path.stat().st_size
        except FileNotFoundError:
            raise FileNotFoundError(f"File {name} not found")
    
    def url(self, name: str) -> str:
        """Get URL for file (not implemented for temp storage)"""
        raise NotImplementedError("SessionFileStorage does not support URLs")
    
    def accessed_time(self, name: str):
        """Get last accessed time"""
        full_path = self.base_path / name
        try:
            return full_path.stat().st_atime
        except FileNotFoundError:
            raise FileNotFoundError(f"File {name} not found")
    
    def created_time(self, name: str):
        """Get creation time"""
        full_path = self.base_path / name
        try:
            return full_path.stat().st_ctime
        except FileNotFoundError:
            raise FileNotFoundError(f"File {name} not found")
    
    def modified_time(self, name: str):
        """Get modification time"""
        full_path = self.base_path / name
        try:
            return full_path.stat().st_mtime
        except FileNotFoundError:
            raise FileNotFoundError(f"File {name} not found")
    
    def listdir(self, path: str = ''):
        """List directory contents"""
        full_path = self.base_path / path if path else self.base_path
        
        if not full_path.exists():
            return [], []
        
        directories = []
        files = []
        
        for item in full_path.iterdir():
            if item.is_dir():
                directories.append(item.name)
            else:
                files.append(item.name)
        
        return directories, files
    
    def path(self, name: str) -> str:
        """Get absolute path to file"""
        return str(self.base_path / name)
    
    def get_available_name(self, name: str, max_length: Optional[int] = None) -> str:
        """Get available filename by adding suffix if needed"""
        if not self.exists(name):
            return name
        
        base, ext = os.path.splitext(name)
        counter = 1
        
        while True:
            new_name = f"{base}_{counter}{ext}"
            if not self.exists(new_name):
                return new_name
            counter += 1
            
            if max_length and len(new_name) > max_length:
                # Truncate base name if too long
                max_base_length = max_length - len(ext) - len(f"_{counter}")
                base = base[:max_base_length]
                new_name = f"{base}_{counter}{ext}"
    
    def save_uploaded_file(self, uploaded_file) -> str:
        """Save Django UploadedFile and return relative path"""
        return self._save(uploaded_file.name, uploaded_file)
    
    def save_content(self, name: str, content: bytes) -> str:
        """Save raw content and return relative path"""
        content_file = ContentFile(content)
        return self._save(name, content_file)
    
    def cleanup_session(self):
        """Clean up all files in this session"""
        if not self.base_path.exists():
            return
        
        files_deleted = 0
        for file_path in self.base_path.rglob('*'):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    files_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {file_path}: {str(e)}")
        
        # Remove directory if empty
        try:
            self.base_path.rmdir()
        except OSError:
            pass  # Directory not empty
        
        logger.info(f"Cleaned up {files_deleted} files from session {self.session_id}")
    
    def get_session_size(self) -> int:
        """Get total size of all files in session"""
        if not self.base_path.exists():
            return 0
        
        total_size = 0
        for file_path in self.base_path.rglob('*'):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass  # File might have been deleted
        
        return total_size
    
    def get_file_list(self) -> list:
        """Get list of all files in session with metadata"""
        if not self.base_path.exists():
            return []
        
        files = []
        for file_path in self.base_path.rglob('*'):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    relative_path = file_path.relative_to(self.base_path)
                    files.append({
                        'name': file_path.name,
                        'path': str(relative_path),
                        'size': stat.st_size,
                        'created': stat.st_ctime,
                        'modified': stat.st_mtime
                    })
                except OSError:
                    pass  # File might have been deleted
        
        return files


class TempFileManager:
    """Utility class for managing temporary files across sessions"""
    
    @staticmethod
    def cleanup_expired_files(hours: int = 24):
        """Clean up files older than specified hours"""
        import time
        from datetime import timedelta
        
        if not settings.TEMP_FILE_ROOT.exists():
            return 0
        
        cutoff_time = time.time() - (hours * 3600)
        deleted_count = 0
        
        for session_dir in settings.TEMP_FILE_ROOT.iterdir():
            if not session_dir.is_dir():
                continue
            
            # Check if session directory is old
            try:
                dir_mtime = session_dir.stat().st_mtime
                if dir_mtime < cutoff_time:
                    # Delete all files in directory
                    for file_path in session_dir.rglob('*'):
                        if file_path.is_file():
                            try:
                                file_path.unlink()
                                deleted_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete expired file {file_path}: {str(e)}")
                    
                    # Remove directory
                    try:
                        session_dir.rmdir()
                    except OSError:
                        pass
            except OSError:
                pass
        
        logger.info(f"Cleaned up {deleted_count} expired temporary files")
        return deleted_count
    
    @staticmethod
    def get_total_storage_usage() -> dict:
        """Get storage usage statistics"""
        if not settings.TEMP_FILE_ROOT.exists():
            return {
                'total_size': 0,
                'session_count': 0,
                'file_count': 0,
                'sessions': []
            }
        
        total_size = 0
        session_count = 0
        file_count = 0
        sessions = []
        
        for session_dir in settings.TEMP_FILE_ROOT.iterdir():
            if not session_dir.is_dir():
                continue
            
            session_count += 1
            session_size = 0
            session_files = 0
            
            for file_path in session_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        size = file_path.stat().st_size
                        session_size += size
                        session_files += 1
                    except OSError:
                        pass
            
            total_size += session_size
            file_count += session_files
            
            sessions.append({
                'session_id': session_dir.name,
                'size': session_size,
                'file_count': session_files
            })
        
        return {
            'total_size': total_size,
            'session_count': session_count,
            'file_count': file_count,
            'sessions': sessions
        }