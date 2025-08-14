"""
Word Parser Tool for SmolAgents

This tool allows the agent to parse Word documents and extract content.
"""

from smolagents import Tool
from apps.documents.parsers.word_parser import WordParser
from apps.documents.storage import SessionFileStorage
from apps.documents.models import Document, DocumentSession
from django.contrib.sessions.models import Session
from typing import Dict, Any
import logging
import pandas as pd
from pathlib import Path
import uuid
import json

logger = logging.getLogger(__name__)


class ParseWordTool(Tool):
    """
    A tool that allows the agent to parse Word documents and extract structured content.
    
    This tool can:
    - Extract text content from Word documents
    - Parse tables and structured data
    - Extract headers and document structure
    - Generate metadata and summaries
    """
    
    name = "parse_word"
    description = """
    Extract text, tables, and headers from Word documents (.docx).
    
    Usage: parse_word(file_path="path/to/document.docx")
    
    Example:
    parse_word(file_path="contracts/agreement.docx")
    
    Returns:
    {
        'status': 'success',
        'text': 'Full document text content...',
        'tables': [{'headers': ['Name', 'Value'], 'rows': [['Item1', '100']]}],
        'headers': ['Chapter 1', 'Section 1.1', 'Conclusion'],
        'metadata': {'pages': 5, 'word_count': 1200, 'author': 'Legal Team'},
        'summary': 'Document contains contract terms and conditions...'
    }
    
    Use this tool to extract and analyze content from Word documents.
    """
    
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the Word document to parse (filename or relative path)"
        }
    }
    
    output_type = "object"
    
    def __init__(self, session_id: str = None):
        """Initialize Word parser tool with optional session context"""
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
    
    def _generate_preview_files(self, content, original_filename: str) -> list:
        """Generate downloadable preview files from Word content"""
        artifacts = []
        
        try:
            # Create preview directory
            preview_dir = Path.cwd() / 'temp' / 'previews'
            preview_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate a unique ID for this parsing session
            session_id = uuid.uuid4().hex[:8]
            base_name = Path(original_filename).stem
            
            # Create text file with extracted content
            text_filename = f"{base_name}_text_{session_id}.txt"
            text_path = preview_dir / text_filename
            
            full_text = '\n'.join(content.paragraphs)
            text_path.write_text(full_text, encoding='utf-8')
            
            if text_path.exists() and text_path.stat().st_size > 0:
                artifacts.append({
                    'type': 'text_extract',
                    'path': str(text_path),
                    'name': f"Text Extract - {base_name}"
                })
                logger.info(f"Generated text extract: {text_path}")
            
            # Create CSV files for tables if they exist
            if content.tables:
                for i, table in enumerate(content.tables):
                    if table.get('rows'):
                        table_filename = f"{base_name}_table_{i+1}_{session_id}.csv"
                        table_path = preview_dir / table_filename
                        
                        # Convert table to DataFrame
                        if table.get('headers') and table.get('rows'):
                            df = pd.DataFrame(table['rows'], columns=table['headers'])
                        else:
                            # If no headers, just use the rows
                            df = pd.DataFrame(table['rows'])
                        
                        df.to_csv(table_path, index=False)
                        
                        if table_path.exists() and table_path.stat().st_size > 0:
                            artifacts.append({
                                'type': 'table_data',
                                'path': str(table_path),
                                'name': f"Table {i+1} - {base_name}"
                            })
                            logger.info(f"Generated table CSV: {table_path}")
            
            # Create structured data file (JSON) with all extracted information
            if content.headers or content.metadata:
                json_filename = f"{base_name}_structure_{session_id}.json"
                json_path = preview_dir / json_filename
                
                structured_data = {
                    'headers': content.headers,
                    'metadata': content.metadata,
                    'table_count': len(content.tables) if content.tables else 0,
                    'paragraph_count': len(content.paragraphs),
                    'word_count': len(full_text.split())
                }
                
                json_path.write_text(json.dumps(structured_data, indent=2), encoding='utf-8')
                
                if json_path.exists() and json_path.stat().st_size > 0:
                    artifacts.append({
                        'type': 'document_structure',
                        'path': str(json_path),
                        'name': f"Document Structure - {base_name}"
                    })
                    logger.info(f"Generated structure file: {json_path}")
                    
        except Exception as e:
            logger.error(f"Error generating preview files: {str(e)}")
        
        return artifacts

    def forward(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Word document and return structured content with downloadable previews.
        
        Args:
            file_path (str): Path to the Word document (filename or relative path)
            
        Returns:
            Dict[str, Any]: Parsed content with text, tables, headers, metadata, summary, and artifacts
        """
        try:
            # Resolve the actual file path
            resolved_path = self._resolve_file_path(file_path)
            logger.info(f"Parsing Word: {file_path} -> {resolved_path}")
            
            content = WordParser.parse(resolved_path)
            
            # Generate preview files
            artifacts = self._generate_preview_files(content, file_path)
            
            result = {
                'status': 'success',
                'text': '\n'.join(content.paragraphs),
                'tables': content.tables,
                'headers': content.headers,
                'metadata': content.metadata,
                'summary': WordParser.generate_summary(content),
                'artifacts': artifacts
            }
            
            # Add artifact paths to result for orchestrator extraction
            if artifacts:
                result['generated_files'] = [artifact['path'] for artifact in artifacts]
                result['message'] = f"Word document parsed successfully. Generated {len(artifacts)} preview file(s)."
            
            return result
            
        except Exception as e:
            logger.error(f"Error in parse_word tool: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }