"""
Word Preview Generator

This utility generates HTML previews from Word documents using the mammoth library.
"""

import mammoth
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import html
import re

logger = logging.getLogger(__name__)


class WordPreviewGenerator:
    """Generate HTML previews from Word documents"""
    
    @staticmethod
    def generate_preview(file_path: str, max_length: Optional[int] = 10000) -> Dict[str, Any]:
        """
        Generate HTML preview from Word document
        
        Args:
            file_path: Path to the Word document
            max_length: Maximum length of HTML content (characters)
            
        Returns:
            Dict with preview_html, success status, and any errors
        """
        try:
            path = Path(file_path)
            
            # Verify file exists and is a Word document
            if not path.exists():
                return {
                    'success': False,
                    'error': 'File not found',
                    'preview_html': None
                }
            
            if not path.suffix.lower() == '.docx':
                return {
                    'success': False,
                    'error': 'File is not a Word document (.docx)',
                    'preview_html': None
                }
            
            # Convert document to HTML using mammoth
            with open(file_path, 'rb') as docx_file:
                result = mammoth.convert_to_html(docx_file)
                html_content = result.value
                warnings = result.messages
            
            # Log any warnings from mammoth
            if warnings:
                logger.warning(f"Mammoth conversion warnings for {file_path}: {warnings}")
            
            # Clean and sanitize HTML
            cleaned_html = WordPreviewGenerator._clean_html(html_content)
            
            # Truncate if too long
            if max_length and len(cleaned_html) > max_length:
                truncated_html = cleaned_html[:max_length]
                # Try to end at a complete tag
                last_close_tag = truncated_html.rfind('>')
                if last_close_tag > max_length - 100:  # If close to the end
                    truncated_html = truncated_html[:last_close_tag + 1]
                
                truncated_html += '<div class="preview-truncated"><em>Preview truncated... Download to view full document.</em></div>'
                cleaned_html = truncated_html
            
            return {
                'success': True,
                'error': None,
                'preview_html': cleaned_html,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Error generating Word preview for {file_path}: {str(e)}")
            return {
                'success': False,
                'error': f"Preview generation failed: {str(e)}",
                'preview_html': None
            }
    
    @staticmethod
    def _clean_html(html_content: str) -> str:
        """
        Clean and sanitize HTML content for safe display
        
        Args:
            html_content: Raw HTML from mammoth conversion
            
        Returns:
            Cleaned HTML content
        """
        # Remove potentially dangerous elements and attributes
        # This is a basic sanitization - for production you might want to use bleach
        
        # Remove script tags and content
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove style attributes that might conflict with our CSS
        html_content = re.sub(r'style\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
        
        # Remove potentially dangerous attributes
        dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus']
        for attr in dangerous_attrs:
            html_content = re.sub(rf'{attr}\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
        
        # Add classes to common elements for styling
        html_content = WordPreviewGenerator._add_preview_classes(html_content)
        
        return html_content.strip()
    
    @staticmethod
    def _add_preview_classes(html_content: str) -> str:
        """
        Add CSS classes to HTML elements for consistent styling
        
        Args:
            html_content: HTML content to process
            
        Returns:
            HTML with added classes
        """
        # Add classes to common elements
        replacements = [
            (r'<h1([^>]*)>', r'<h1\1 class="preview-h1">'),
            (r'<h2([^>]*)>', r'<h2\1 class="preview-h2">'),
            (r'<h3([^>]*)>', r'<h3\1 class="preview-h3">'),
            (r'<h4([^>]*)>', r'<h4\1 class="preview-h4">'),
            (r'<h5([^>]*)>', r'<h5\1 class="preview-h5">'),
            (r'<h6([^>]*)>', r'<h6\1 class="preview-h6">'),
            (r'<p([^>]*)>', r'<p\1 class="preview-paragraph">'),
            (r'<table([^>]*)>', r'<table\1 class="preview-table">'),
            (r'<ul([^>]*)>', r'<ul\1 class="preview-list">'),
            (r'<ol([^>]*)>', r'<ol\1 class="preview-list preview-ordered">'),
            (r'<blockquote([^>]*)>', r'<blockquote\1 class="preview-quote">'),
        ]
        
        for pattern, replacement in replacements:
            html_content = re.sub(pattern, replacement, html_content, flags=re.IGNORECASE)
        
        return html_content
    
    @staticmethod
    def extract_text_summary(file_path: str, max_chars: int = 500) -> str:
        """
        Extract plain text summary from Word document
        
        Args:
            file_path: Path to the Word document
            max_chars: Maximum number of characters to return
            
        Returns:
            Plain text summary
        """
        try:
            with open(file_path, 'rb') as docx_file:
                result = mammoth.extract_raw_text(docx_file)
                text = result.value.strip()
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Truncate if necessary
            if len(text) > max_chars:
                text = text[:max_chars].rsplit(' ', 1)[0] + '...'
            
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return "Could not extract text preview"


class WordPreviewValidator:
    """Validate Word documents before preview generation"""
    
    @staticmethod
    def validate_word_file(file_path: str) -> Dict[str, Any]:
        """
        Validate that a file is a proper Word document
        
        Args:
            file_path: Path to check
            
        Returns:
            Dict with validation results
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    'valid': False,
                    'error': 'File does not exist'
                }
            
            if not path.suffix.lower() == '.docx':
                return {
                    'valid': False,
                    'error': 'File is not a Word document (.docx)'
                }
            
            # Try to open with mammoth to validate format
            try:
                with open(file_path, 'rb') as docx_file:
                    mammoth.extract_raw_text(docx_file)
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Invalid Word document format: {str(e)}'
                }
            
            return {
                'valid': True,
                'error': None
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }