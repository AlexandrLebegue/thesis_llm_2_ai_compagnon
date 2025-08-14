"""
PDF Parser Tool for SmolAgents

This tool allows the agent to parse PDF files and extract text, tables, and metadata.
"""

from smolagents import Tool
from apps.documents.parsers.pdf_parser import PDFParser
from apps.documents.storage import SessionFileStorage
from apps.documents.models import Document, DocumentSession
from django.contrib.sessions.models import Session
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ParsePDFTool(Tool):
    """
    A tool that allows the agent to parse PDF files and extract structured content.
    
    This tool can:
    - Extract text from PDF files
    - Parse tables and structured data
    - Generate metadata and summaries
    - Handle multi-page documents
    """
    
    name = "parse_pdf"
    description = """
    Extract text, tables, and metadata from PDF files.
    
    Usage: parse_pdf(file_path="path/to/document.pdf")
    
    Example:
    parse_pdf(file_path="documents/report.pdf")
    
    Returns:
    {
        'status': 'success',
        'text': 'Full document text content...',
        'tables': [{'headers': [...], 'rows': [...]}],
        'metadata': {'pages': 10, 'title': 'Report Title', 'author': 'John Doe'},
        'summary': 'Auto-generated summary of document content...'
    }
    
    Use this tool to extract and analyze content from PDF documents.
    """
    
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the PDF file to parse (filename or relative path)"
        }
    }
    
    output_type = "object"
    
    def __init__(self, session_id: str = None):
        """Initialize PDF parser tool with optional session context"""
        super().__init__()
        self.session_id = session_id
    
    def _resolve_file_path(self, file_path: str) -> str:
        """
        Resolve file path to actual storage location.
        
        Args:
            file_path (str): Input file path (could be filename or relative path)
            
        Returns:
            str: Absolute path to the file
        """
        # If file_path is already absolute and exists, use it directly
        import os
        if os.path.isabs(file_path) and os.path.exists(file_path):
            return file_path
        
        # Try to find file in session storage if session_id is available
        if self.session_id:
            try:
                storage = SessionFileStorage(session_id=self.session_id)
                resolved_path = storage.path(file_path)
                if os.path.exists(resolved_path):
                    return resolved_path
            except Exception as e:
                logger.warning(f"Failed to resolve path via session storage: {str(e)}")
        
        # Try to find document by name in database
        try:
            # Look for document with this filename in any session
            document = Document.objects.filter(
                original_name=file_path,
                status='ready'
            ).first()
            
            if document:
                session_key = document.session.session.session_key
                storage = SessionFileStorage(session_id=session_key)
                resolved_path = storage.path(document.file_path)
                if os.path.exists(resolved_path):
                    return resolved_path
        except Exception as e:
            logger.warning(f"Failed to resolve path via database lookup: {str(e)}")
        
        # Return original path as fallback
        return file_path
    
    def forward(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PDF file and return structured content.
        
        Args:
            file_path (str): Path to the PDF file (filename or relative path)
            
        Returns:
            Dict[str, Any]: Parsed content with text, tables, metadata, and summary
        """
        try:
            # Resolve the actual file path
            resolved_path = self._resolve_file_path(file_path)
            logger.info(f"Parsing PDF: {file_path} -> {resolved_path}")
            
            content = PDFParser.parse(resolved_path)
            return {
                'status': 'success',
                'text': content.text,
                'tables': content.tables,
                'metadata': content.metadata,
                'summary': PDFParser.generate_summary(content)
            }
        except Exception as e:
            logger.error(f"Error in parse_pdf tool: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }