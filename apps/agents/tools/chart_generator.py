import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import pandas as pd
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

class ChartGenerator:
    """Generate charts using matplotlib"""
    
    CHART_TYPES = ['bar', 'line', 'pie', 'scatter', 'histogram', 'area']
    
    @staticmethod
    def generate_chart(
        data: Dict[str, Any],
        chart_type: str = 'bar',
        title: str = '',
        xlabel: str = '',
        ylabel: str = '',
        save_path: Optional[str] = None
    ) -> str:
        """
        Generate a chart from data specification
        
        Args:
            data: Dictionary with 'x' and 'y' keys for data
            chart_type: Type of chart to generate
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            save_path: Optional path to save the chart
            
        Returns:
            Path to saved chart image
        """
        
        if chart_type not in ChartGenerator.CHART_TYPES:
            raise ValueError(f"Unsupported chart type: {chart_type}. Supported types: {ChartGenerator.CHART_TYPES}")
        
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Extract data
            x_data = data.get('x', [])
            y_data = data.get('y', [])
            
            # Generate chart based on type
            if chart_type == 'bar':
                ax.bar(x_data, y_data)
            elif chart_type == 'line':
                ax.plot(x_data, y_data, marker='o')
            elif chart_type == 'pie':
                ax.pie(y_data, labels=x_data, autopct='%1.1f%%')
            elif chart_type == 'scatter':
                ax.scatter(x_data, y_data)
            elif chart_type == 'histogram':
                ax.hist(y_data, bins=20, edgecolor='black')
            elif chart_type == 'area':
                ax.fill_between(x_data, y_data, alpha=0.5)
                ax.plot(x_data, y_data)
            
            # Set labels and title
            if title:
                ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel and chart_type != 'pie':
                ax.set_xlabel(xlabel)
            if ylabel and chart_type != 'pie':
                ax.set_ylabel(ylabel)
            
            # Improve layout
            plt.tight_layout()
            
            # Save chart
            if not save_path:
                # Use a cross-platform temp directory within the project
                charts_dir = Path.cwd() / 'temp' / 'charts'
                charts_dir.mkdir(parents=True, exist_ok=True)
                save_path = charts_dir / f"chart_{uuid.uuid4().hex}.png"
            
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            return str(save_path)
            
        except Exception as e:
            logger.error(f"Error generating chart: {str(e)}")
            raise
    
    @staticmethod
    def generate_from_dataframe(
        df: pd.DataFrame,
        chart_type: str = 'bar',
        x_column: str = None,
        y_columns: List[str] = None,
        **kwargs
    ) -> str:
        """Generate chart from pandas DataFrame"""
        
        if x_column and y_columns:
            data = {
                'x': df[x_column].tolist(),
                'y': df[y_columns[0]].tolist() if len(y_columns) == 1 else [df[col].tolist() for col in y_columns]
            }
        else:
            # Auto-detect columns
            data = {
                'x': list(range(len(df))),
                'y': df.iloc[:, 0].tolist()
            }
        
        return ChartGenerator.generate_chart(data, chart_type, **kwargs)