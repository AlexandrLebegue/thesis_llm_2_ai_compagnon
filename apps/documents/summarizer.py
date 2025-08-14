import logging
from typing import Dict, List, Any, Optional
from apps.documents.parsers import PDFParser, ExcelParser, WordParser, PDFContent, ExcelContent, WordContent
from apps.documents.models import Document, DocumentSession
import re

logger = logging.getLogger(__name__)

class DocumentSummarizer:
    """Create summaries for different document types to manage context"""
    
    MAX_SUMMARY_LENGTH = 500
    MAX_CONTEXT_DOCUMENTS = 20
    
    @staticmethod
    def summarize_document(document: Document) -> Dict[str, Any]:
        """Generate a comprehensive summary for a document"""
        try:
            file_path = document.get_file_path()
            doc_type = document.document_type.lower()
            
            if doc_type == 'pdf':
                content = PDFParser.parse(file_path)
                return DocumentSummarizer._summarize_pdf(content, document)
            elif doc_type in ['xlsx', 'xls']:
                content = ExcelParser.parse(file_path)
                return DocumentSummarizer._summarize_excel(content, document)
            elif doc_type in ['docx', 'doc']:
                content = WordParser.parse(file_path)
                return DocumentSummarizer._summarize_word(content, document)
            else:
                return {
                    'type': 'unknown',
                    'name': document.original_name,
                    'summary': f"Unknown document type: {doc_type}",
                    'metadata': {}
                }
                
        except Exception as e:
            logger.error(f"Error summarizing document {document.id}: {str(e)}")
            return {
                'type': 'error',
                'name': document.original_name,
                'summary': f"Error processing document: {str(e)}",
                'metadata': {}
            }
    
    @staticmethod
    def _summarize_pdf(content: PDFContent, document: Document) -> Dict[str, Any]:
        """Summarize PDF content"""
        summary_parts = []
        
        # Basic info
        summary_parts.append(f"PDF with {content.page_count} pages")
        
        # Metadata
        if content.metadata.get('title'):
            summary_parts.append(f"Title: {content.metadata['title']}")
        if content.metadata.get('author'):
            summary_parts.append(f"Author: {content.metadata['author']}")
        
        # Tables
        if content.tables:
            summary_parts.append(f"Contains {len(content.tables)} tables")
        
        # Text analysis
        word_count = len(content.text.split())
        summary_parts.append(f"Approximately {word_count} words")
        
        # Key topics (simple keyword extraction)
        keywords = DocumentSummarizer._extract_keywords(content.text)
        if keywords:
            summary_parts.append(f"Key topics: {', '.join(keywords[:5])}")
        
        # Text preview
        text_preview = DocumentSummarizer._clean_text(content.text[:200])
        if text_preview:
            summary_parts.append(f"Preview: {text_preview}...")
        
        return {
            'type': 'pdf',
            'name': document.original_name,
            'summary': ' | '.join(summary_parts)[:DocumentSummarizer.MAX_SUMMARY_LENGTH],
            'metadata': {
                'page_count': content.page_count,
                'table_count': len(content.tables),
                'word_count': word_count,
                'keywords': keywords[:10],
                **content.metadata
            }
        }
    
    @staticmethod
    def _summarize_excel(content: ExcelContent, document: Document) -> Dict[str, Any]:
        """Summarize Excel content"""
        summary_parts = []
        
        # Basic info
        sheet_count = content.metadata['sheet_count']
        total_rows = content.metadata['total_rows']
        summary_parts.append(f"Excel with {sheet_count} sheets, {total_rows} total rows")
        
        # Sheet details
        sheet_details = []
        for sheet_name, df in list(content.sheets.items())[:3]:  # First 3 sheets
            row_count = len(df)
            col_count = len(df.columns)
            sheet_details.append(f"{sheet_name} ({row_count}x{col_count})")
        
        if sheet_details:
            summary_parts.append(f"Sheets: {', '.join(sheet_details)}")
        
        # Data types
        numeric_sheets = [name for name in content.summary_stats.keys()]
        if numeric_sheets:
            summary_parts.append(f"Numeric data in: {', '.join(numeric_sheets[:3])}")
        
        # Column preview
        all_columns = []
        for df in list(content.sheets.values())[:2]:  # First 2 sheets
            all_columns.extend(list(df.columns)[:3])  # First 3 columns each
        
        if all_columns:
            unique_columns = list(dict.fromkeys(all_columns))[:5]  # Remove duplicates, limit to 5
            summary_parts.append(f"Key columns: {', '.join(map(str, unique_columns))}")
        
        return {
            'type': 'excel',
            'name': document.original_name,
            'summary': ' | '.join(summary_parts)[:DocumentSummarizer.MAX_SUMMARY_LENGTH],
            'metadata': {
                'sheet_names': content.metadata['sheet_names'],
                'total_rows': total_rows,
                'total_columns': content.metadata['total_columns'],
                'numeric_sheets': numeric_sheets,
                'sample_columns': all_columns[:10]
            }
        }
    
    @staticmethod
    def _summarize_word(content: WordContent, document: Document) -> Dict[str, Any]:
        """Summarize Word content"""
        summary_parts = []
        
        # Basic info
        para_count = content.metadata['paragraph_count']
        word_count = content.metadata['word_count']
        summary_parts.append(f"Word document with {para_count} paragraphs, {word_count} words")
        
        # Metadata
        if content.metadata.get('title'):
            summary_parts.append(f"Title: {content.metadata['title']}")
        if content.metadata.get('author'):
            summary_parts.append(f"Author: {content.metadata['author']}")
        
        # Structure
        if content.headers:
            summary_parts.append(f"{len(content.headers)} headings")
            # Preview headings
            heading_preview = ', '.join(content.headers[:3])
            summary_parts.append(f"Sections: {heading_preview}")
        
        if content.tables:
            summary_parts.append(f"Contains {len(content.tables)} tables")
        
        # Key topics
        full_text = ' '.join(content.paragraphs)
        keywords = DocumentSummarizer._extract_keywords(full_text)
        if keywords:
            summary_parts.append(f"Key topics: {', '.join(keywords[:5])}")
        
        # Text preview
        if content.paragraphs:
            text_preview = DocumentSummarizer._clean_text(' '.join(content.paragraphs[:2])[:200])
            summary_parts.append(f"Preview: {text_preview}...")
        
        return {
            'type': 'word',
            'name': document.original_name,
            'summary': ' | '.join(summary_parts)[:DocumentSummarizer.MAX_SUMMARY_LENGTH],
            'metadata': {
                'paragraph_count': para_count,
                'word_count': word_count,
                'header_count': len(content.headers),
                'table_count': len(content.tables),
                'keywords': keywords[:10],
                'headers': content.headers[:5],
                **{k: v for k, v in content.metadata.items() if k not in ['paragraph_count', 'word_count']}
            }
        }
    
    @staticmethod
    def create_session_context(session: DocumentSession) -> Dict[str, Any]:
        """Create a comprehensive context for all documents in a session"""
        try:
            documents = session.documents.filter(
                processing_status='completed'
            ).order_by('-created_at')[:DocumentSummarizer.MAX_CONTEXT_DOCUMENTS]
            
            context = {
                'document_count': documents.count(),
                'documents': [],
                'total_pages': 0,
                'total_words': 0,
                'document_types': {},
                'all_keywords': [],
                'session_summary': ''
            }
            
            # Process each document
            for doc in documents:
                doc_summary = DocumentSummarizer.summarize_document(doc)
                context['documents'].append(doc_summary)
                
                # Aggregate statistics
                doc_type = doc_summary['type']
                context['document_types'][doc_type] = context['document_types'].get(doc_type, 0) + 1
                
                metadata = doc_summary.get('metadata', {})
                context['total_pages'] += metadata.get('page_count', 0)
                context['total_words'] += metadata.get('word_count', 0)
                
                keywords = metadata.get('keywords', [])
                context['all_keywords'].extend(keywords)
            
            # Create session summary
            summary_parts = []
            summary_parts.append(f"{context['document_count']} documents")
            
            if context['document_types']:
                type_summary = ', '.join([f"{count} {doc_type}" for doc_type, count in context['document_types'].items()])
                summary_parts.append(f"Types: {type_summary}")
            
            if context['total_pages']:
                summary_parts.append(f"{context['total_pages']} total pages")
            
            if context['total_words']:
                summary_parts.append(f"~{context['total_words']:,} words")
            
            # Most common keywords
            if context['all_keywords']:
                keyword_freq = {}
                for keyword in context['all_keywords']:
                    keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
                
                top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:5]
                summary_parts.append(f"Key topics: {', '.join([k for k, _ in top_keywords])}")
            
            context['session_summary'] = ' | '.join(summary_parts)
            
            return context
            
        except Exception as e:
            logger.error(f"Error creating session context: {str(e)}")
            return {
                'document_count': 0,
                'documents': [],
                'session_summary': f"Error creating context: {str(e)}"
            }
    
    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text using simple frequency analysis"""
        if not text:
            return []
        
        # Clean and normalize text
        text = DocumentSummarizer._clean_text(text.lower())
        
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
            'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their'
        }
        
        # Extract words (3+ characters)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        words = [word for word in words if word not in stop_words]
        
        # Count frequency
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Return most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:max_keywords] if freq > 1]
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean text by removing extra whitespace and special characters"""
        if not text:
            return ""
        
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?;:-]', '', text)
        
        return text.strip()