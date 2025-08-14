"""
Word Modifier Tool for SmolAgents

This tool allows the agent to modify Word documents and insert content.
"""

from smolagents import Tool
from apps.agents.tools.word_modifier import WordModifier
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ModifyWordTool(Tool):
    """
    A tool that allows the agent to modify Word documents and insert content.
    
    This tool can:
    - Modify existing Word documents
    - Add new paragraphs and headings
    - Insert tables and data
    - Add images and charts
    - Apply formatting and styling
    """
    
    name = "modify_word"
    description = """
    Modify existing Word documents by adding text, tables, images, and formatting.
    
    Usage: modify_word(file_path="path/to/doc.docx", instructions="JSON_string", images="[image_paths]")
    
    Example - Add heading and paragraph:
    modify_word(
        file_path="docs/report.docx",
        instructions='{"content": [{"type": "heading", "text": "New Section", "level": 1}, {"type": "paragraph", "text": "This is new content."}]}'
    )
    
    Example - Add table:
    modify_word(
        file_path="docs/data.docx",
        instructions='{"content": [{"type": "table", "headers": ["Name", "Value"], "rows": [["Item A", "100"], ["Item B", "200"]]}]}'
    )
    
    Example - Add image:
    modify_word(
        file_path="docs/report.docx",
        instructions='{"content": [{"type": "image", "caption": "Sales Chart"}]}',
        images='["charts/sales_chart.png"]'
    )
    
    JSON Format:
    {
        "content": [
            {"type": "heading", "text": "Title", "level": 1},
            {"type": "paragraph", "text": "Content text"},
            {"type": "table", "headers": ["Col1", "Col2"], "rows": [["A", "B"]]},
            {"type": "image", "caption": "Image caption"},
            {"type": "page_break"}
        ]
    }
    
    Returns: {"status": "success", "output_path": "path/to/modified_doc.docx"}
    """
    
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the Word document to modify"
        },
        "instructions": {
            "type": "string",
            "description": "JSON string with modification instructions (see description for format)"
        },
        "images": {
            "type": "string",
            "description": "JSON array of image file paths: '[\"path1.png\", \"path2.jpg\"]' (optional)",
            "nullable": True
        }
    }
    
    output_type = "object"
    
    def forward(self, file_path: str, instructions: str, images: Optional[str] = None) -> Dict[str, Any]:
        """
        Modify Word document based on instructions.
        
        Args:
            file_path (str): Path to the Word document
            instructions (str): JSON string with modification instructions
            images (str, optional): JSON array of image paths
            
        Returns:
            Dict[str, Any]: Result with output path and status
        """
        try:
            import json
            instruction_dict = json.loads(instructions) if isinstance(instructions, str) else instructions
            image_list = json.loads(images) if images else None
            
            output_path = WordModifier.modify_word(file_path, instruction_dict, image_list)
            
            return {
                'status': 'success',
                'output_path': output_path,
                'message': f'Word document modified successfully: {Path(output_path).name}'
            }
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing instructions JSON: {str(e)}")
            return {
                'status': 'error',
                'error': f'Invalid JSON instructions: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error in modify_word tool: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }