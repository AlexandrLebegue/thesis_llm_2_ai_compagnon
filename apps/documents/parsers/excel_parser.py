import pandas as pd
import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ExcelContent:
    sheets: Dict[str, pd.DataFrame]
    metadata: Dict[str, Any]
    summary_stats: Dict[str, Any]

class ExcelParser:
    """Parse and analyze Excel files"""
    
    @staticmethod
    def parse(file_path: str) -> ExcelContent:
        """Parse Excel file and extract all sheets"""
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            sheets = {}
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                sheets[sheet_name] = df
            
            # Generate metadata
            metadata = {
                'sheet_count': len(sheets),
                'sheet_names': excel_file.sheet_names,
                'total_rows': sum(len(df) for df in sheets.values()),
                'total_columns': sum(len(df.columns) for df in sheets.values()),
            }
            
            # Generate summary statistics for numeric columns
            summary_stats = {}
            for sheet_name, df in sheets.items():
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    summary_stats[sheet_name] = {
                        'numeric_columns': list(numeric_cols),
                        'summary': df[numeric_cols].describe().to_dict()
                    }
            
            return ExcelContent(
                sheets=sheets,
                metadata=metadata,
                summary_stats=summary_stats
            )
            
        except Exception as e:
            logger.error(f"Error parsing Excel {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def generate_summary(content: ExcelContent, max_length: int = 500) -> str:
        """Generate a summary of the Excel content"""
        summary_parts = []
        
        # Basic info
        summary_parts.append(
            f"Excel file with {content.metadata['sheet_count']} sheets, "
            f"{content.metadata['total_rows']} total rows"
        )
        
        # Sheet details
        for sheet_name, df in list(content.sheets.items())[:3]:  # First 3 sheets
            columns = list(df.columns)[:5]  # First 5 columns
            summary_parts.append(
                f"Sheet '{sheet_name}': {len(df)} rows, columns: {', '.join(map(str, columns))}"
            )
        
        return ' | '.join(summary_parts)[:max_length]