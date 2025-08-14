import os
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

# Try to import magic, but handle gracefully if not available
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False


class FileUploadValidationMiddleware(MiddlewareMixin):
    """Validate file uploads before processing"""
    
    def process_request(self, request):
        if request.method == 'POST' and request.FILES:
            for field_name, uploaded_file in request.FILES.items():
                # Check file extension
                ext = os.path.splitext(uploaded_file.name)[1].lower()
                if ext not in settings.ALLOWED_FILE_EXTENSIONS:
                    return JsonResponse({
                        'error': f'File type {ext} not allowed. Allowed types: {", ".join(settings.ALLOWED_FILE_EXTENSIONS)}'
                    }, status=400)
                
                # Check file size
                if uploaded_file.size > settings.MAX_FILE_SIZE:
                    max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
                    return JsonResponse({
                        'error': f'File size exceeds maximum of {max_size_mb}MB'
                    }, status=400)
                
                # Check MIME type (basic validation) - only if magic is available
                if MAGIC_AVAILABLE:
                    try:
                        file_header = uploaded_file.read(1024)
                        uploaded_file.seek(0)  # Reset file pointer
                        mime_type = magic.from_buffer(file_header, mime=True)
                        
                        allowed_mimes = {
                            '.pdf': 'application/pdf',
                            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        }
                        
                        if ext in allowed_mimes and mime_type != allowed_mimes[ext]:
                            return JsonResponse({
                                'error': 'File content does not match file extension'
                            }, status=400)
                            
                    except Exception:
                        # If magic fails, continue with basic extension check
                        pass
        
        return None