"""
Excel Modifier Tool for SmolAgents

This tool allows the agent to modify Excel files and add charts.
"""

from smolagents import Tool
from apps.agents.tools.excel_modifier import ExcelModifier
from typing import Dict, Any
from pathlib import Path
import logging

# Import our robust utility functions
from .tool_utils import (
    ToolInputSanitizer, ToolValidator, FileVerifier,
    DebugLogger, ErrorFormatter, ToolOutputSanitizer
)
from .excel_preview import ExcelPreviewGenerator

logger = logging.getLogger(__name__)


class ModifyExcelTool(Tool):
    """
    A tool that allows the agent to modify Excel files and add charts.
    
    This tool can:
    - Modify existing Excel files
    - Add new data and sheets
    - Insert charts and visualizations
    - Apply formatting and formulas
    """
    
    name = "modify_excel"
    description = """
    Modify existing Excel files by adding data, sheets, charts, and formulas.
    Creates new files if the source doesn't exist. Supports both single and double quotes in JSON.
    
    Example usage:
    modify_excel(
        file_path="data/sales.xlsx",
        instructions='{"operations": [{"type": "add_sheet", "name": "Sales", "data": [["Product", "Price"], ["Widget A", 29.99]]}]}'
    )
    
    JSON Format supports multiple operation formats:
    
    Operations format:
    {
        "operations": [
            {"type": "add_sheet", "name": "SheetName", "data": [["header1", "header2"], ["val1", "val2"]]},
            {"type": "add_data", "sheet": "SheetName", "data": [["new_data"]]},
            {"type": "add_chart", "sheet": "SheetName", "chart_type": "bar", "title": "Chart"}
        ]
    }
    
    Direct format:
    {
        "add_sheets": [{"name": "SheetName", "data": [["header", "value"]]}],
        "add_charts": [{"sheet": "SheetName", "type": "bar", "title": "Chart"}]
    }
    
    Returns: {"status": "success", "output_path": "path/to/modified_file.xlsx"}
    """
    
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the Excel file to modify"
        },
        "instructions": {
            "type": "string",
            "description": "JSON string with modification instructions (see description for format)"
        }
    }
    
    output_type = "object"
    
    def forward(self, file_path: str, instructions: str) -> Dict[str, Any]:
        """
        Modify Excel file based on instructions with robust input handling.
        
        Args:
            file_path (str): Path to the Excel file (will create if doesn't exist)
            instructions (str): JSON string with modification instructions
            
        Returns:
            Dict[str, Any]: Result with output path and status
        """
        # Initialize debug logging
        DebugLogger.log_tool_start('modify_excel', {
            'file_path': file_path,
            'instructions_length': len(str(instructions))
        })
        
        try:
            # Robust JSON parsing with multiple fallback strategies
            instruction_dict = ToolInputSanitizer.safe_json_loads(
                instructions,
                fallback_value={'operations': []}
            )
            
            DebugLogger.log_json_parsing('modify_excel', str(instructions), instruction_dict)
            
            # Validate input structure
            is_valid, validation_error = ToolValidator.validate_input(instruction_dict, 'excel_modifier')
            if not is_valid:
                DebugLogger.log_validation_result('modify_excel', False, validation_error)
                result = {
                    'status': 'error',
                    'error': ErrorFormatter.format_validation_error('modify_excel', validation_error)
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'modify_excel')
            
            DebugLogger.log_validation_result('modify_excel', True)
            
            # Check if source file exists
            source_exists = Path(file_path).exists() if file_path else False
            logger.debug(f"Source file exists: {source_exists}")
            
            # Add validation for empty instructions
            if not instruction_dict or (
                not instruction_dict.get('operations') and
                not instruction_dict.get('add_sheets') and
                not instruction_dict.get('add_data') and
                not instruction_dict.get('add_charts')
            ):
                result = {
                    'status': 'error',
                    'error': 'No valid operations found in instructions. Please provide operations, add_sheets, add_data, or add_charts.'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'modify_excel')
            
            # Modify Excel file
            output_path = ExcelModifier.modify_excel(file_path, instruction_dict)
            
            # Verify file creation
            verification = FileVerifier.verify_excel_file(output_path)
            DebugLogger.log_file_operation(
                'modify_excel',
                'modification',
                output_path,
                verification['exists'] and verification['has_data'],
                f"Sheets: {len(verification.get('sheets', []))}, Size: {verification.get('size', 0)} bytes"
            )
            
            if not verification['exists']:
                result = {
                    'status': 'error',
                    'error': ErrorFormatter.format_file_creation_error('modify_excel', output_path, verification)
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'modify_excel')
            
            if not verification['has_data']:
                logger.warning("Excel file modified but appears to have no data")
                result = {
                    'status': 'success',
                    'output_path': output_path,
                    'message': f'Excel file created but may be empty: {Path(output_path).name}',
                    'warning': 'File appears to have no data'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'modify_excel')
            
            # Generate HTML preview
            preview_result = ExcelPreviewGenerator.generate_preview(output_path)
            preview_html = None
            if preview_result['success']:
                preview_html = preview_result['preview_html']
                logger.info(f"Generated HTML preview for modified Excel file")
            else:
                logger.warning(f"Failed to generate preview: {preview_result.get('error', 'Unknown error')}")
            
            result = {
                'status': 'success',
                'output_path': output_path,
                'preview_html': preview_html,
                'message': f'Excel file modified successfully: {Path(output_path).name}'
            }
            
            # Sanitize output to prevent framework parsing issues
            return ToolOutputSanitizer.sanitize_tool_output(result, 'modify_excel')
            
        except Exception as e:
            logger.error(f"Error in modify_excel tool: {str(e)}", exc_info=True)
            if "json" in str(e).lower():
                result = {
                    'status': 'error',
                    'error': ErrorFormatter.format_json_error('modify_excel', str(instructions), e)
                }
            else:
                result = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Sanitize error output as well
            return ToolOutputSanitizer.sanitize_tool_output(result, 'modify_excel')