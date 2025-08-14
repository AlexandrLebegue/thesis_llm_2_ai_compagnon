from django.core.exceptions import ValidationError
from django.conf import settings
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def validate_file_upload(uploaded_file):
    """
    Validate uploaded file for type, size, and security
    
    Args:
        uploaded_file: Django UploadedFile instance
        
    Raises:
        ValueError: If file validation fails
    """
    
    # Check file size
    if uploaded_file.size > settings.MAX_FILE_SIZE:
        max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
        raise ValueError(f'File too large. Maximum size is {max_size_mb}MB')
    
    # Check file extension
    file_ext = Path(uploaded_file.name).suffix.lower()
    if file_ext not in settings.ALLOWED_FILE_EXTENSIONS:
        allowed_exts = ', '.join(settings.ALLOWED_FILE_EXTENSIONS)
        raise ValueError(f'File type not allowed. Allowed types: {allowed_exts}')
    
    # Check MIME type (if python-magic is available)
    try:
        # Read first chunk to check file type
        file_chunk = uploaded_file.read(1024)
        uploaded_file.seek(0)  # Reset file pointer
        
        # Basic MIME type validation
        expected_types = {
            '.pdf': [b'%PDF'],
            '.xlsx': [b'PK\x03\x04'],  # ZIP-based format
            '.docx': [b'PK\x03\x04']   # ZIP-based format
        }
        
        if file_ext in expected_types:
            signatures = expected_types[file_ext]
            if not any(file_chunk.startswith(sig) for sig in signatures):
                logger.warning(f"File {uploaded_file.name} may not match its extension")
                # Don't fail validation, just log warning
        
    except Exception as e:
        logger.warning(f"Could not validate MIME type for {uploaded_file.name}: {str(e)}")
    
    # Check filename for security
    filename = uploaded_file.name
    if not filename or '..' in filename or '/' in filename or '\\' in filename:
        raise ValueError('Invalid filename')
    
    # Check for suspicious patterns
    suspicious_patterns = ['..', '__', 'script', 'exec', 'eval']
    filename_lower = filename.lower()
    if any(pattern in filename_lower for pattern in suspicious_patterns):
        raise ValueError('Filename contains suspicious patterns')


def validate_file_content(file_path: str, expected_type: str) -> bool:
    """
    Validate file content matches expected type
    
    Args:
        file_path: Path to file
        expected_type: Expected file type (pdf, xlsx, docx)
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return False
        
        # Read file header
        with open(path, 'rb') as f:
            header = f.read(1024)
        
        # Check based on expected type
        if expected_type == 'pdf':
            return header.startswith(b'%PDF')
        elif expected_type in ['xlsx', 'docx']:
            return header.startswith(b'PK\x03\x04')  # ZIP signature
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating file content {file_path}: {str(e)}")
        return False


def get_file_type_from_content(file_path: str) -> str:
    """
    Determine file type from content
    
    Args:
        file_path: Path to file
        
    Returns:
        str: File type (pdf, xlsx, docx, unknown)
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(1024)
        
        if header.startswith(b'%PDF'):
            return 'pdf'
        elif header.startswith(b'PK\x03\x04'):
            # Need to check ZIP content for Office files
            import zipfile
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_file:
                    file_list = zip_file.namelist()
                    if 'xl/workbook.xml' in file_list:
                        return 'xlsx'
                    elif 'word/document.xml' in file_list:
                        return 'docx'
            except:
                pass
            return 'zip'
        
        return 'unknown'
        
    except Exception as e:
        logger.error(f"Error determining file type for {file_path}: {str(e)}")
        return 'unknown'


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    import re
    
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove or replace special characters
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Ensure reasonable length
    if len(filename) > 255:
        name, ext = Path(filename).stem, Path(filename).suffix
        max_name_length = 255 - len(ext) - 1
        filename = name[:max_name_length] + ext
    
    return filename