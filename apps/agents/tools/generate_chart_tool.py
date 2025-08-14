"""
Chart Generator Tool for SmolAgents

This tool allows the agent to create charts and visualizations from data.
"""

from smolagents import Tool
from apps.agents.tools.chart_generator import ChartGenerator
from typing import Dict, Any
from pathlib import Path
import logging
import json

# Import our robust utility functions
from .tool_utils import (
    ToolInputSanitizer, ToolValidator, FileVerifier,
    DebugLogger, ErrorFormatter, ToolOutputSanitizer
)

logger = logging.getLogger(__name__)


class GenerateChartTool(Tool):
    """
    A tool that allows the agent to create charts and visualizations from data.
    
    This tool can:
    - Generate various types of charts (bar, line, pie, scatter, etc.)
    - Create visualizations from data sets
    - Apply custom styling and formatting
    - Save charts as image files
    """
    
    name = "generate_chart"
    description = """
    Create charts and visualizations from data (bar, line, pie, scatter plots).
    
    This tool accepts data_spec as either a JSON string or a Python dict object for maximum compatibility.
    
    Example usage with JSON string:
    generate_chart(data_spec='{"type": "bar", "title": "Sales by Product", "data": {"x": ["Product A", "Product B"], "y": [100, 150]}}')
    
    Example usage with dict object:
    generate_chart(data_spec={"type": "bar", "title": "Sales by Product", "data": {"x": ["Product A", "Product B"], "y": [100, 150]}})
    
    Supported chart types:
    - "bar": Vertical bar chart
    - "line": Line chart for trends
    - "pie": Pie chart for proportions
    - "scatter": Scatter plot for correlations
    
    Data Format (JSON string or dict):
    {
        "type": "bar|line|pie|scatter",
        "title": "Chart Title",
        "data": {
            "x": ["label1", "label2"],           // For bar/line/scatter
            "y": [value1, value2],               // For bar/line/scatter
            "labels": ["item1", "item2"],        // For pie charts
            "values": [value1, value2]           // For pie charts
        },
        "xlabel": "X-axis label",
        "ylabel": "Y-axis label",
        "save_path": "optional/custom/path.png"
    }
    
    Returns: {"status": "success", "chart_path": "path/to/generated_chart.png"}
    """
    
    inputs = {
        "data_spec": {
            "type": "any",
            "description": "Chart configuration as JSON string or dict object (see description for format)"
        }
    }
    
    output_type = "object"
    
    def forward(self, data_spec) -> Dict[str, Any]:
        """
        Generate chart from data specification with robust input handling.
        
        Args:
            data_spec: JSON string or dict with chart configuration
            
        Returns:
            Dict[str, Any]: Result with chart path and status
        """
        # Initialize debug logging
        DebugLogger.log_tool_start('generate_chart', {
            'data_spec_type': type(data_spec).__name__,
            'data_spec_length': len(str(data_spec))
        })
        
        try:
            # Handle both string and object inputs
            if isinstance(data_spec, dict):
                # Already a Python object - use directly
                spec = data_spec
                logger.info("Chart tool received dict input directly")
            elif isinstance(data_spec, str):
                # JSON string - parse it
                spec = ToolInputSanitizer.safe_json_loads(
                    data_spec,
                    fallback_value={'type': 'bar', 'data': {}}
                )
                logger.info("Chart tool received string input, parsed as JSON")
            else:
                # Convert to string and try to parse
                logger.warning(f"Chart tool received unexpected input type: {type(data_spec)}")
                spec = ToolInputSanitizer.safe_json_loads(
                    str(data_spec),
                    fallback_value={'type': 'bar', 'data': {}}
                )
            
            DebugLogger.log_json_parsing('generate_chart', str(data_spec), spec)
            
            # Validate input structure
            is_valid, validation_error = ToolValidator.validate_input(spec, 'chart_generator')
            if not is_valid:
                DebugLogger.log_validation_result('generate_chart', False, validation_error)
                result = {
                    'status': 'error',
                    'error': ErrorFormatter.format_validation_error('generate_chart', validation_error)
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'generate_chart')
            
            DebugLogger.log_validation_result('generate_chart', True)
            
            # Ensure required fields have defaults
            chart_type = spec.get('type', 'bar')
            chart_data = spec.get('data', {})
            
            # Validate chart data based on type
            if chart_type in ['bar', 'line', 'scatter']:
                if 'x' not in chart_data or 'y' not in chart_data:
                    result = {
                        'status': 'error',
                        'error': f'Chart type "{chart_type}" requires "x" and "y" data arrays'
                    }
                    return ToolOutputSanitizer.sanitize_tool_output(result, 'generate_chart')
            elif chart_type == 'pie':
                if 'labels' not in chart_data or 'values' not in chart_data:
                    result = {
                        'status': 'error',
                        'error': 'Pie charts require "labels" and "values" data arrays'
                    }
                    return ToolOutputSanitizer.sanitize_tool_output(result, 'generate_chart')
            
            # Generate chart
            chart_path = ChartGenerator.generate_chart(
                data=chart_data,
                chart_type=chart_type,
                title=spec.get('title', f'{chart_type.title()} Chart'),
                xlabel=spec.get('xlabel', ''),
                ylabel=spec.get('ylabel', ''),
                save_path=spec.get('save_path')
            )
            
            # Verify chart file was created
            chart_exists = Path(chart_path).exists() if chart_path else False
            file_size = Path(chart_path).stat().st_size if chart_exists else 0
            
            DebugLogger.log_file_operation(
                'generate_chart',
                'creation',
                chart_path,
                chart_exists and file_size > 0,
                f"Size: {file_size} bytes"
            )
            
            if not chart_exists:
                result = {
                    'status': 'error',
                    'error': f'Chart file was not created: {chart_path}'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'generate_chart')
            
            if file_size == 0:
                result = {
                    'status': 'error',
                    'error': f'Chart file is empty: {chart_path}'
                }
                return ToolOutputSanitizer.sanitize_tool_output(result, 'generate_chart')
            
            result = {
                'status': 'success',
                'chart_path': chart_path,
                'message': f'Chart generated successfully: {Path(chart_path).name}'
            }
            
            # Sanitize output to prevent framework parsing issues
            return ToolOutputSanitizer.sanitize_tool_output(result, 'generate_chart')
            
        except Exception as e:
            logger.error(f"Error in generate_chart tool: {str(e)}", exc_info=True)
            if "json" in str(e).lower():
                result = {
                    'status': 'error',
                    'error': ErrorFormatter.format_json_error('generate_chart', str(data_spec), e)
                }
            else:
                result = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Sanitize error output as well
            return ToolOutputSanitizer.sanitize_tool_output(result, 'generate_chart')