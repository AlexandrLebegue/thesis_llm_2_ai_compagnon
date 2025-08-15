"""
Excel Parser Tool for SmolAgents

This tool allows the agent to parse Excel files and extract data from sheets.
"""

from smolagents import Tool
from apps.documents.parsers.excel_parser import ExcelParser
from apps.documents.storage import SessionFileStorage
from apps.documents.models import Document, DocumentSession
from django.contrib.sessions.models import Session
from typing import Dict, Any
import logging
import pandas as pd
from pathlib import Path
import uuid
from .excel_preview import ExcelPreviewGenerator

logger = logging.getLogger(__name__)


class ParseExcelTool(Tool):
    """
    A tool that allows the agent to parse Excel files and extract structured data.
    
    This tool can:
    - Read data from multiple Excel sheets
    - Extract structured data and metadata
    - Generate summaries of spreadsheet content
    - Handle various Excel formats
    """
    
    name = "parse_excel"
    description = """
    Extract data from all sheets in Excel files (.xlsx, .xls).
    
    Usage: parse_excel(file_path="path/to/spreadsheet.xlsx")
    
    Example:
    parse_excel(file_path="data/sales_report.xlsx")
    
    Returns:
    {
        'status': 'success',
        'sheets': {
            'Sales Data': [{'Product': 'A', 'Revenue': 1000}, ...],
            'Summary': [{'Total': 5000, 'Average': 250}, ...]
        },
        'metadata': {'sheet_count': 2, 'total_rows': 150},
        'summary': 'Excel file contains sales data with 2 sheets...'
    }
    
    Use this tool to extract and analyze data from Excel spreadsheets.
    """
    
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the Excel file to parse (filename or relative path)"
        }
    }
    
    output_type = "object"
    
    def __init__(self, session_id: str = None):
        """Initialize Excel parser tool with optional session context"""
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
        """Generate downloadable preview files from Excel content"""
        artifacts = []
        
        try:
            # Create preview directory
            preview_dir = Path.cwd() / 'temp' / 'previews'
            preview_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate a unique ID for this parsing session
            session_id = uuid.uuid4().hex[:8]
            base_name = Path(original_filename).stem
            
            # Create CSV files for each sheet
            for sheet_name, df in content.sheets.items():
                if not df.empty:
                    # Sanitize sheet name for filename
                    safe_sheet_name = "".join(c for c in sheet_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    csv_filename = f"{base_name}_{safe_sheet_name}_{session_id}.csv"
                    csv_path = preview_dir / csv_filename
                    
                    # Save as CSV
                    df.to_csv(csv_path, index=False)
                    
                    if csv_path.exists() and csv_path.stat().st_size > 0:
                        artifacts.append({
                            'type': 'data_preview',
                            'path': str(csv_path),
                            'name': f"Data Preview - {sheet_name}",
                            'sheet_name': sheet_name
                        })
                        logger.info(f"Generated CSV preview: {csv_path}")
            
            # Create a summary file with all sheets combined (if multiple sheets)
            if len(content.sheets) > 1:
                summary_filename = f"{base_name}_summary_{session_id}.csv"
                summary_path = preview_dir / summary_filename
                
                # Combine first few rows from each sheet
                combined_data = []
                for sheet_name, df in content.sheets.items():
                    if not df.empty:
                        # Add sheet identifier column
                        preview_df = df.head(10).copy()
                        preview_df.insert(0, 'Sheet', sheet_name)
                        combined_data.append(preview_df)
                
                if combined_data:
                    combined_df = pd.concat(combined_data, ignore_index=True)
                    combined_df.to_csv(summary_path, index=False)
                    
                    if summary_path.exists() and summary_path.stat().st_size > 0:
                        artifacts.append({
                            'type': 'data_summary',
                            'path': str(summary_path),
                            'name': f"Excel Summary - {base_name}"
                        })
                        logger.info(f"Generated summary file: {summary_path}")
                        
        except Exception as e:
            logger.error(f"Error generating preview files: {str(e)}")
        
        return artifacts

    def forward(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Excel file and return structured data with downloadable previews.
        
        Args:
            file_path (str): Path to the Excel file (filename or relative path)
            
        Returns:
            Dict[str, Any]: Parsed content with sheets, metadata, summary, and artifacts
        """
        try:
            # Resolve the actual file path
            resolved_path = self._resolve_file_path(file_path)
            logger.info(f"Parsing Excel: {file_path} -> {resolved_path}")
            
            content = ExcelParser.parse(resolved_path)
            
            # Generate preview files
            artifacts = self._generate_preview_files(content, file_path)
            
            # Generate HTML preview
            preview_result = ExcelPreviewGenerator.generate_preview(resolved_path)
            preview_html = None
            if preview_result['success']:
                preview_html = preview_result['preview_html']
                logger.info(f"Generated HTML preview for {file_path}")
            else:
                logger.warning(f"Failed to generate preview for {file_path}: {preview_result.get('error', 'Unknown error')}")
            
            result = {
                'status': 'success',
                'sheets': {name: df.to_dict('records') for name, df in content.sheets.items()},
                'metadata': content.metadata,
                'summary': ExcelParser.generate_summary(content),
                'artifacts': artifacts,
                'preview_html': preview_html
            }
            
            # Add artifact paths to result for orchestrator extraction
            if artifacts:
                result['generated_files'] = [artifact['path'] for artifact in artifacts]
                result['message'] = f"Excel parsed successfully. Generated {len(artifacts)} preview file(s)."
            
            return result
            
        except Exception as e:
            logger.error(f"Error in parse_excel tool: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }