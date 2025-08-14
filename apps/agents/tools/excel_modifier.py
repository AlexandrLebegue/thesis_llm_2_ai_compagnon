import pandas as pd
from xlsxwriter import Workbook
from xlsxwriter.chart import Chart
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ExcelModifier:
    """Modify Excel files and add charts"""
    
    @staticmethod
    def modify_excel(
        file_path: str,
        instructions: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """
        Modify Excel file based on instructions
        
        Supports multiple instruction formats:
        1. Operations format:
        {
            'operations': [
                {'type': 'add_sheet', 'name': 'NewSheet'},
                {'type': 'add_data', 'sheet': 'Sheet1', 'data': [[...]]},
                {'type': 'add_chart', 'sheet': 'Sheet1', 'chart_type': 'column'},
            ]
        }
        
        2. Direct format:
        {
            'add_sheets': [{'name': 'Sheet1', 'data': [[...]]}],
            'add_charts': [{'sheet': 'Sheet1', 'type': 'column', 'title': 'Chart'}]
        }
        """
        try:
            # Read existing Excel file if it exists
            sheets = {}
            if file_path and Path(file_path).exists():
                excel_file = pd.ExcelFile(file_path)
                sheets = {name: pd.read_excel(excel_file, sheet_name=name)
                         for name in excel_file.sheet_names}
            
            # Generate output path
            if not output_path:
                # Use cross-platform temp directory within project
                outputs_dir = Path.cwd() / 'temp' / 'outputs'
                outputs_dir.mkdir(parents=True, exist_ok=True)
                
                if file_path and Path(file_path).exists():
                    output_path = outputs_dir / f"modified_{Path(file_path).stem}.xlsx"
                else:
                    output_path = outputs_dir / "new_spreadsheet.xlsx"
            
            # Convert instructions to operations format if needed
            operations = ExcelModifier._normalize_instructions(instructions)
            
            # Create new workbook with XlsxWriter
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Write existing sheets first
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Process operations
                for operation in operations:
                    op_type = operation['type']
                    
                    if op_type == 'add_sheet':
                        sheet_name = operation.get('name', f'Sheet_{len(sheets) + 1}')
                        data = operation.get('data', [])
                        
                        # Handle various data formats
                        processed_data = ExcelModifier._process_data_safely(data)
                        
                        if processed_data:
                            try:
                                # Create DataFrame from processed data
                                if len(processed_data) > 1 and isinstance(processed_data[0], (list, tuple)):
                                    # First row as headers, rest as data
                                    headers = processed_data[0]
                                    data_rows = processed_data[1:] if len(processed_data) > 1 else []
                                    df = pd.DataFrame(data_rows, columns=headers)
                                else:
                                    # Single row or no headers
                                    df = pd.DataFrame(processed_data)
                                
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                                logger.debug(f"Added sheet '{sheet_name}' with {len(df)} rows")
                            except Exception as e:
                                logger.warning(f"Error creating DataFrame for sheet '{sheet_name}': {e}")
                                # Fallback: create empty sheet
                                worksheet = workbook.add_worksheet(sheet_name)
                        else:
                            # Create empty sheet if no data
                            worksheet = workbook.add_worksheet(sheet_name)
                            logger.debug(f"Created empty sheet '{sheet_name}'")
                        
                    elif op_type == 'add_data':
                        sheet_name = operation.get('sheet', 'Sheet1')
                        data = operation.get('data', [])
                        
                        # Handle various data formats
                        processed_data = ExcelModifier._process_data_safely(data)
                        
                        if processed_data:
                            try:
                                if sheet_name in sheets:
                                    # Append to existing sheet
                                    existing_df = sheets[sheet_name]
                                    
                                    # Create new DataFrame
                                    if len(processed_data) > 1 and isinstance(processed_data[0], (list, tuple)):
                                        headers = processed_data[0]
                                        data_rows = processed_data[1:] if len(processed_data) > 1 else []
                                        new_df = pd.DataFrame(data_rows, columns=headers)
                                    else:
                                        new_df = pd.DataFrame(processed_data)
                                    
                                    # Combine DataFrames
                                    combined_df = pd.concat([existing_df, new_df], ignore_index=True, sort=False)
                                    combined_df.to_excel(writer, sheet_name=sheet_name, index=False)
                                else:
                                    # Create new sheet with data
                                    if len(processed_data) > 1 and isinstance(processed_data[0], (list, tuple)):
                                        headers = processed_data[0]
                                        data_rows = processed_data[1:] if len(processed_data) > 1 else []
                                        df = pd.DataFrame(data_rows, columns=headers)
                                    else:
                                        df = pd.DataFrame(processed_data)
                                    
                                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                                
                                logger.debug(f"Added data to sheet '{sheet_name}'")
                            except Exception as e:
                                logger.warning(f"Error adding data to sheet '{sheet_name}': {e}")
                        else:
                            logger.warning(f"No valid data provided for sheet '{sheet_name}'")
                    
                    elif op_type == 'add_chart':
                        sheet_name = operation['sheet']
                        if sheet_name in writer.sheets:
                            ExcelModifier._add_chart(
                                workbook,
                                writer.sheets[sheet_name],
                                operation
                            )
                    
                    elif op_type == 'add_formula':
                        sheet_name = operation['sheet']
                        if sheet_name in writer.sheets:
                            worksheet = writer.sheets[sheet_name]
                            worksheet.write_formula(operation['cell'], operation['formula'])
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error modifying Excel: {str(e)}")
            raise
    
    @staticmethod
    def _normalize_instructions(instructions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert various instruction formats to normalized operations list
        """
        operations = []
        
        # If already in operations format, return as-is
        if 'operations' in instructions:
            return instructions['operations']
        
        # Handle direct format
        # Add sheets
        if 'add_sheets' in instructions:
            for sheet in instructions['add_sheets']:
                operations.append({
                    'type': 'add_sheet',
                    'name': sheet['name'],
                    'data': sheet.get('data', [])
                })
        
        # Add data to existing sheets
        if 'add_data' in instructions:
            for data_config in instructions['add_data']:
                operations.append({
                    'type': 'add_data',
                    'sheet': data_config['sheet'],
                    'data': data_config['data'],
                    'start_cell': data_config.get('start_cell', 'A1')
                })
        
        # Add charts
        if 'add_charts' in instructions:
            for chart in instructions['add_charts']:
                operations.append({
                    'type': 'add_chart',
                    'sheet': chart['sheet'],
                    'chart_type': chart.get('type', 'column'),
                    'title': chart.get('title', 'Chart'),
                    'categories_range': chart.get('categories_range'),
                    'values_range': chart.get('values_range'),
                    'position': chart.get('position', 'E2')
                })
        
        # Add formulas
        if 'add_formulas' in instructions:
            for formula in instructions['add_formulas']:
                operations.append({
                    'type': 'add_formula',
                    'sheet': formula['sheet'],
                    'cell': formula['cell'],
                    'formula': formula['formula']
                })
        
        # Handle legacy single operations
        if 'add_sheet' in instructions:
            operations.append({
                'type': 'add_sheet',
                'name': instructions['add_sheet'].get('name', 'Sheet1'),
                'data': instructions['add_sheet'].get('data', [])
            })
        
        return operations
    
    @staticmethod
    def _process_data_safely(data: Any) -> List[List]:
        """
        Safely process various data formats into a consistent list of lists.
        Handles empty data, malformed structures, and various input types.
        """
        if not data:
            return []
        
        # Handle pandas DataFrame
        if hasattr(data, 'values') and hasattr(data, 'columns'):
            try:
                result = data.values.tolist()
                # Prepend column names as first row
                result.insert(0, list(data.columns))
                return result
            except Exception as e:
                logger.warning(f"Error processing DataFrame: {e}")
                return []
        
        # Handle list of dictionaries
        if isinstance(data, list) and data and isinstance(data[0], dict):
            try:
                keys = list(data[0].keys())
                result = [keys]  # Headers
                for item in data:
                    if isinstance(item, dict):
                        result.append([item.get(key, '') for key in keys])
                    else:
                        logger.warning(f"Expected dict, got {type(item)}: {item}")
                return result
            except Exception as e:
                logger.warning(f"Error processing list of dicts: {e}")
                return []
        
        # Handle nested lists/arrays
        if isinstance(data, list):
            result = []
            for row in data:
                if isinstance(row, (list, tuple)):
                    result.append(list(row))
                elif isinstance(row, dict):
                    result.append(list(row.values()))
                elif row is not None:
                    result.append([str(row)])
                else:
                    result.append([''])
            return result
        
        # Handle single values
        if data is not None:
            return [[str(data)]]
        
        return []
    
    @staticmethod
    def _add_chart(workbook: Workbook, worksheet, config: Dict[str, Any]):
        """Add chart to worksheet"""
        chart_type_map = {
            'column': 'column',
            'bar': 'bar',
            'line': 'line',
            'pie': 'pie',
            'scatter': 'scatter',
            'area': 'area',
        }
        
        chart_type = chart_type_map.get(config.get('chart_type', 'column'))
        chart = workbook.add_chart({'type': chart_type})
        
        # Configure chart
        chart.add_series({
            'name': config.get('series_name', 'Series 1'),
            'categories': config.get('categories_range'),
            'values': config.get('values_range'),
        })
        
        chart.set_title({'name': config.get('title', 'Chart')})
        chart.set_x_axis({'name': config.get('x_axis_label', '')})
        chart.set_y_axis({'name': config.get('y_axis_label', '')})
        
        # Insert chart
        position = config.get('position', 'E2')
        worksheet.insert_chart(position, chart)