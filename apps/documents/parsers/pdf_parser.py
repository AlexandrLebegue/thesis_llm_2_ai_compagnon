import logging
from typing import Dict, List, Any
import pdfplumber
import PyPDF2
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PDFContent:
    text: str
    tables: List[List[List[str]]]
    metadata: Dict[str, Any]
    page_count: int

class PDFParser:
    """Extract text and tables from PDF files"""
    
    @staticmethod
    def parse(file_path: str) -> PDFContent:
        """Parse PDF and extract content"""
        try:
            text_content = []
            tables = []
            metadata = {}
            
            # Extract text and tables with pdfplumber
            with pdfplumber.open(file_path) as pdf:
                metadata['page_count'] = len(pdf.pages)
                
                for page in pdf.pages:
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
                    
                    # Extract tables
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
            
            # Extract metadata with PyPDF2
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                if pdf_reader.metadata:
                    metadata.update({
                        'title': pdf_reader.metadata.get('/Title', ''),
                        'author': pdf_reader.metadata.get('/Author', ''),
                        'subject': pdf_reader.metadata.get('/Subject', ''),
                        'creator': pdf_reader.metadata.get('/Creator', ''),
                        'creation_date': str(pdf_reader.metadata.get('/CreationDate', '')),
                    })
            
            return PDFContent(
                text='\n'.join(text_content),
                tables=tables,
                metadata=metadata,
                page_count=metadata['page_count']
            )
            
        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {str(e)}")
            raise
    
    @staticmethod
    def generate_summary(content: PDFContent, max_length: int = 500) -> str:
        """Generate a summary of the PDF content"""
        summary_parts = []
        
        # Add basic info
        summary_parts.append(f"PDF Document with {content.page_count} pages")
        
        # Add metadata if available
        if content.metadata.get('title'):
            summary_parts.append(f"Title: {content.metadata['title']}")
        
        # Add table info
        if content.tables:
            summary_parts.append(f"Contains {len(content.tables)} tables")
        
        # Add text preview
        text_preview = content.text[:300].replace('\n', ' ')
        if text_preview:
            summary_parts.append(f"Preview: {text_preview}...")
        
        return ' | '.join(summary_parts)[:max_length]