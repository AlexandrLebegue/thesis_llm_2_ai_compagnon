"""
Excel Preview Generator

This utility generates HTML previews from Excel documents using pandas.
"""

import pandas as pd
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List
import html
import re

logger = logging.getLogger(__name__)


class ExcelPreviewGenerator:
    """Generate HTML previews from Excel documents"""
    
    @staticmethod
    def generate_preview(file_path: str, max_rows_per_sheet: Optional[int] = 100) -> Dict[str, Any]:
        """
        Generate HTML preview from Excel document
        
        Args:
            file_path: Path to the Excel document
            max_rows_per_sheet: Maximum number of rows to display per sheet
            
        Returns:
            Dict with preview_html, success status, and any errors
        """
        try:
            path = Path(file_path)
            
            # Verify file exists and is an Excel document
            if not path.exists():
                return {
                    'success': False,
                    'error': 'File not found',
                    'preview_html': None
                }
            
            if not path.suffix.lower() in ['.xlsx', '.xls']:
                return {
                    'success': False,
                    'error': 'File is not an Excel document (.xlsx or .xls)',
                    'preview_html': None
                }
            
            # Read Excel file
            excel_file = pd.ExcelFile(file_path)
            sheets_html = []
            
            # Process each sheet
            for sheet_name in excel_file.sheet_names[:10]:  # Limit to first 10 sheets
                try:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    
                    # Skip empty sheets
                    if df.empty:
                        continue
                    
                    # Truncate large datasets
                    is_truncated = False
                    if len(df) > max_rows_per_sheet:
                        df = df.head(max_rows_per_sheet)
                        is_truncated = True
                    
                    # Generate sheet HTML
                    sheet_html = ExcelPreviewGenerator._generate_sheet_html(
                        df, sheet_name, is_truncated, len(excel_file.sheet_names) > 1
                    )
                    sheets_html.append(sheet_html)
                    
                except Exception as e:
                    logger.warning(f"Error processing sheet '{sheet_name}': {str(e)}")
                    continue
            
            if not sheets_html:
                return {
                    'success': False,
                    'error': 'No readable sheets found in Excel file',
                    'preview_html': None
                }
            
            # Combine all sheets into final HTML
            if len(sheets_html) == 1:
                # Single sheet - display directly
                preview_html = sheets_html[0]
            else:
                # Multiple sheets - create tabbed interface
                preview_html = ExcelPreviewGenerator._create_tabbed_interface(sheets_html, excel_file.sheet_names)
            
            return {
                'success': True,
                'error': None,
                'preview_html': preview_html,
                'sheet_count': len(excel_file.sheet_names)
            }
            
        except Exception as e:
            logger.error(f"Error generating Excel preview for {file_path}: {str(e)}")
            return {
                'success': False,
                'error': f"Preview generation failed: {str(e)}",
                'preview_html': None
            }
    
    @staticmethod
    def _generate_sheet_html(df: pd.DataFrame, sheet_name: str, is_truncated: bool, is_multi_sheet: bool) -> str:
        """Generate HTML for a single sheet"""
        try:
            # Generate basic statistics
            stats_html = ExcelPreviewGenerator._generate_stats_html(df)
            
            # Convert DataFrame to HTML
            table_html = df.to_html(
                classes='preview-excel-table',
                table_id=f'sheet-{sheet_name.replace(" ", "-").lower()}',
                escape=False,
                index=False,
                max_rows=None,
                max_cols=None
            )
            
            # Clean and enhance the table HTML
            table_html = ExcelPreviewGenerator._enhance_table_html(table_html)
            
            # Build sheet container
            sheet_html = f"""
            <div class="excel-sheet-container" data-sheet="{html.escape(sheet_name)}">
                {f'<h4 class="preview-sheet-title">{html.escape(sheet_name)}</h4>' if is_multi_sheet else ''}
                {stats_html}
                <div class="excel-table-wrapper">
                    {table_html}
                </div>
                {f'<div class="preview-truncated"><em>Showing first {len(df)} rows. Download to view full spreadsheet.</em></div>' if is_truncated else ''}
            </div>
            """
            
            return sheet_html
            
        except Exception as e:
            logger.error(f"Error generating sheet HTML for '{sheet_name}': {str(e)}")
            return f'<div class="preview-error">Error displaying sheet "{html.escape(sheet_name)}"</div>'
    
    @staticmethod
    def _generate_stats_html(df: pd.DataFrame) -> str:
        """Generate summary statistics HTML"""
        try:
            stats = []
            
            # Basic info
            stats.append(f"{len(df)} rows")
            stats.append(f"{len(df.columns)} columns")
            
            # Numeric columns info
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                stats.append(f"{len(numeric_cols)} numeric columns")
            
            # Date columns info
            date_cols = df.select_dtypes(include=['datetime64']).columns
            if len(date_cols) > 0:
                stats.append(f"{len(date_cols)} date columns")
            
            stats_text = " • ".join(stats)
            
            return f'<div class="excel-sheet-stats">{stats_text}</div>'
            
        except Exception as e:
            logger.warning(f"Error generating stats: {str(e)}")
            return ""
    
    @staticmethod
    def _enhance_table_html(table_html: str) -> str:
        """Clean and enhance table HTML with better classes"""
        # Add responsive wrapper classes
        table_html = table_html.replace(
            'class="preview-excel-table"',
            'class="preview-excel-table table-auto w-full text-sm"'
        )
        
        # Enhance headers
        table_html = re.sub(
            r'<th([^>]*)>',
            r'<th\1 class="preview-excel-header">',
            table_html
        )
        
        # Enhance cells
        table_html = re.sub(
            r'<td([^>]*)>',
            r'<td\1 class="preview-excel-cell">',
            table_html
        )
        
        # Handle NaN values
        table_html = table_html.replace('>NaN<', '><span class="text-gray-400">—</span><')
        table_html = table_html.replace('>nan<', '><span class="text-gray-400">—</span><')
        
        return table_html
    
    @staticmethod
    def _create_tabbed_interface(sheets_html: List[str], sheet_names: List[str]) -> str:
        """Create tabbed interface for multiple sheets"""
        try:
            # Generate tab headers
            tabs_html = ['<div class="excel-tabs-container">']
            tabs_html.append('<div class="excel-tabs-header">')
            
            for i, sheet_name in enumerate(sheet_names[:len(sheets_html)]):
                active_class = "active" if i == 0 else ""
                safe_id = sheet_name.replace(" ", "-").replace("'", "").replace('"', '').lower()
                tabs_html.append(
                    f'<button class="excel-tab-button {active_class}" '
                    f'onclick="switchExcelTab(\'{safe_id}\')" '
                    f'data-tab="{safe_id}">{html.escape(sheet_name)}</button>'
                )
            
            tabs_html.append('</div>')
            
            # Generate tab content
            tabs_html.append('<div class="excel-tabs-content">')
            
            for i, (sheet_html, sheet_name) in enumerate(zip(sheets_html, sheet_names[:len(sheets_html)])):
                active_class = "active" if i == 0 else ""
                safe_id = sheet_name.replace(" ", "-").replace("'", "").replace('"', '').lower()
                tabs_html.append(
                    f'<div class="excel-tab-content {active_class}" id="tab-{safe_id}">'
                    f'{sheet_html}</div>'
                )
            
            tabs_html.append('</div>')
            tabs_html.append('</div>')
            
            return '\n'.join(tabs_html)
            
        except Exception as e:
            logger.error(f"Error creating tabbed interface: {str(e)}")
            # Fallback to simple concatenation
            return '\n'.join(sheets_html)
    
    @staticmethod
    def extract_text_summary(file_path: str, max_chars: int = 500) -> str:
        """
        Extract plain text summary from Excel document
        
        Args:
            file_path: Path to the Excel document
            max_chars: Maximum number of characters to return
            
        Returns:
            Plain text summary
        """
        try:
            excel_file = pd.ExcelFile(file_path)
            summary_parts = []
            
            summary_parts.append(f"Excel file with {len(excel_file.sheet_names)} sheets")
            
            # Add info about first few sheets
            for sheet_name in excel_file.sheet_names[:3]:
                try:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    summary_parts.append(
                        f"'{sheet_name}': {len(df)} rows, {len(df.columns)} columns"
                    )
                except Exception:
                    continue
            
            summary = " | ".join(summary_parts)
            
            # Truncate if necessary
            if len(summary) > max_chars:
                summary = summary[:max_chars].rsplit(' ', 1)[0] + '...'
            
            return summary
            
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {str(e)}")
            return "Could not extract text preview"


class ExcelPreviewValidator:
    """Validate Excel documents before preview generation"""
    
    @staticmethod
    def validate_excel_file(file_path: str) -> Dict[str, Any]:
        """
        Validate that a file is a proper Excel document
        
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
            
            if not path.suffix.lower() in ['.xlsx', '.xls']:
                return {
                    'valid': False,
                    'error': 'File is not an Excel document (.xlsx or .xls)'
                }
            
            # Try to open with pandas to validate format
            try:
                pd.ExcelFile(file_path)
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Invalid Excel document format: {str(e)}'
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