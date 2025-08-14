"""
SmolAgents Tools for Ultra PDF Chatbot 3000

This module contains all the SmolAgents Tool classes for document processing.
"""

# Import all SmolAgents tools
from .parse_pdf_tool import ParsePDFTool
from .parse_excel_tool import ParseExcelTool
from .parse_word_tool import ParseWordTool
from .modify_excel_tool import ModifyExcelTool
from .modify_word_tool import ModifyWordTool
from .generate_chart_tool import GenerateChartTool
from .save_artifact_tool import SaveArtifactTool
from .excel_generator_tool import ExcelGeneratorTool

# List of all available tools
__all__ = [
    'ParsePDFTool',
    'ParseExcelTool',
    'ParseWordTool',
    'ModifyExcelTool',
    'ModifyWordTool',
    'GenerateChartTool',
    'SaveArtifactTool',
    'ExcelGeneratorTool'
]

# Tool instances for easy access
AVAILABLE_TOOLS = [
    ParsePDFTool(),
    ParseExcelTool(),
    ParseWordTool(),
    ModifyExcelTool(),
    ModifyWordTool(),
    GenerateChartTool(),
    SaveArtifactTool(),
    ExcelGeneratorTool()
]

def get_tool_by_name(tool_name: str):
    """Get a tool instance by its name"""
    for tool in AVAILABLE_TOOLS:
        if tool.name == tool_name:
            return tool
    return None

def list_tool_names():
    """Get list of all available tool names"""
    return [tool.name for tool in AVAILABLE_TOOLS]