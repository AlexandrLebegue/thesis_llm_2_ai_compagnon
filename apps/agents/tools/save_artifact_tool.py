"""
Save Artifact Tool for SmolAgents

This tool allows the agent to save generated content as downloadable files.
"""

from smolagents import Tool
from typing import Dict, Any
from pathlib import Path
import uuid
import logging

# Import our robust utility functions
from .tool_utils import DebugLogger, ToolOutputSanitizer

logger = logging.getLogger(__name__)


class SaveArtifactTool(Tool):
    """
    A tool that allows the agent to save generated content as downloadable artifacts.
    
    This tool can:
    - Save various types of content as files
    - Generate unique artifact IDs
    - Handle text, binary, and structured data
    - Create downloadable file paths
    """
    
    name = "save_artifact"
    description = """
    Save generated content as downloadable files (text, CSV, JSON, etc.).
    
    Usage: save_artifact(content="data_to_save", file_type="file_extension")
    
    Example - Save text content:
    save_artifact(content="This is a report summary...", file_type="txt")
    
    Example - Save CSV data:
    save_artifact(content="Name,Age,City\\nJohn,25,NYC\\nJane,30,LA", file_type="csv")
    
    Example - Save JSON data:
    save_artifact(content='{"users": [{"name": "John", "age": 25}]}', file_type="json")
    
    Example - Save DataFrame (auto-converts):
    save_artifact(content=dataframe_object, file_type="csv")
    
    Supported file types:
    - "txt" - Plain text files
    - "csv" - Comma-separated values
    - "json" - JSON structured data
    - "xml" - XML formatted data
    - "md" - Markdown files
    
    Returns: {"status": "success", "artifact_id": "unique_id", "path": "temp/artifacts/file.ext"}
    """
    
    inputs = {
        "content": {
            "type": "string",
            "description": "Content to save (text, CSV data, JSON string, etc.)"
        },
        "file_type": {
            "type": "string",
            "description": "File extension: txt, csv, json, xml, md"
        }
    }
    
    output_type = "object"
    
    def forward(self, content: Any, file_type: str) -> Dict[str, Any]:
        """
        Save content as artifact for download with robust error handling.
        
        Args:
            content (Any): Content to save
            file_type (str): File extension for the artifact
            
        Returns:
            Dict[str, Any]: Result with artifact ID, path, and status
        """
        # Initialize debug logging
        DebugLogger.log_tool_start('save_artifact', {
            'content_type': type(content).__name__,
            'content_length': len(str(content)) if content else 0,
            'file_type': file_type
        })
        
        try:
            # Validate inputs
            if content is None or (isinstance(content, str) and not content.strip()):
                result = {
                    'status': 'error',
                    'error': 'Cannot save empty or null content'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'save_artifact')
            
            if not file_type or not isinstance(file_type, str):
                result = {
                    'status': 'error',
                    'error': 'File type must be a non-empty string'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'save_artifact')
            
            # Clean file type
            file_type = file_type.strip().lower().lstrip('.')
            
            # Validate file type
            allowed_types = ['txt', 'csv', 'json', 'xml', 'md', 'html', 'log']
            if file_type not in allowed_types:
                logger.warning(f"Unusual file type: {file_type}, proceeding anyway")
            
            # Generate unique artifact ID
            artifact_id = uuid.uuid4().hex
            
            # Create artifact directory - use cross-platform temp directory within project
            artifact_dir = Path.cwd() / 'temp' / 'artifacts'
            artifact_dir.mkdir(parents=True, exist_ok=True)
            
            # Create artifact path
            artifact_path = artifact_dir / f"{artifact_id}.{file_type}"
            
            # Save content based on type with better error handling
            bytes_written = 0
            
            if isinstance(content, bytes):
                artifact_path.write_bytes(content)
                bytes_written = len(content)
            elif isinstance(content, str):
                artifact_path.write_text(content, encoding='utf-8')
                bytes_written = len(content.encode('utf-8'))
            else:
                # Handle other types (DataFrame, dict, etc.)
                if hasattr(content, 'to_csv') and file_type == 'csv':
                    content.to_csv(artifact_path, index=False)
                    bytes_written = artifact_path.stat().st_size
                elif hasattr(content, 'to_json') and file_type == 'json':
                    content.to_json(artifact_path)
                    bytes_written = artifact_path.stat().st_size
                elif hasattr(content, 'to_dict') and file_type == 'json':
                    import json
                    json_content = json.dumps(content.to_dict(), indent=2)
                    artifact_path.write_text(json_content, encoding='utf-8')
                    bytes_written = len(json_content.encode('utf-8'))
                else:
                    # Convert to string and save
                    str_content = str(content)
                    artifact_path.write_text(str_content, encoding='utf-8')
                    bytes_written = len(str_content.encode('utf-8'))
            
            # Verify file was created and has content
            if not artifact_path.exists():
                result = {
                    'status': 'error',
                    'error': f'Artifact file was not created: {artifact_path}'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'save_artifact')
            
            actual_size = artifact_path.stat().st_size
            if actual_size == 0:
                result = {
                    'status': 'error',
                    'error': f'Artifact file is empty: {artifact_path}'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'save_artifact')
            
            DebugLogger.log_file_operation(
                'save_artifact',
                'creation',
                str(artifact_path),
                True,
                f"Size: {actual_size} bytes"
            )
            
            result = {
                'status': 'success',
                'artifact_id': artifact_id,
                'path': str(artifact_path),
                'message': f'Artifact saved successfully: {artifact_path.name}',
                'file_size': actual_size
            }
            
            # Sanitize output to prevent framework parsing issues
            return ToolOutputSanitizer.sanitize_tool_output(result, 'save_artifact')
            
        except Exception as e:
            logger.error(f"Error in save_artifact tool: {str(e)}", exc_info=True)
            result = {
                'status': 'error',
                'error': str(e)
            }
            
            # Sanitize error output as well
            return ToolOutputSanitizer.sanitize_tool_output(result, 'save_artifact')