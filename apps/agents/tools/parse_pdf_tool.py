"""
AI PDF Tool for SmolAgents

This tool converts PDF parsing to use AI analysis through OpenRouter API.
It allows the agent to extract text from PDF files and query it using AI.
"""

import pymupdf as fitz  # PyMuPDF
import requests
import os
from typing import Dict, Any
from smolagents import Tool
from apps.documents.storage import SessionFileStorage
from apps.documents.models import Document, DocumentSession
from django.contrib.sessions.models import Session
from decouple import config
import logging

logger = logging.getLogger(__name__)


class ParsePDFTool(Tool):
    """
    A tool that allows the agent to extract text from PDF files and query it using AI through OpenRouter API.
    
    This tool combines PDF text extraction with AI analysis to answer questions about PDF content.
    It preserves Django session compatibility while adding AI-powered analysis capabilities.
    """
    
    name = "ai_pdf_analysis"
    description = """
    Extract text from a PDF file and query it using AI through OpenRouter API.
    
    This tool can:
    - Extract text content from PDF files using PyMuPDF
    - Send the extracted content along with a user query to OpenRouter AI
    - Get intelligent responses about the PDF content using Gemini 2.5 Flash model
    - Handle API authentication and error management
    - Work with Django session storage for file resolution
    
    Use this tool when you need to analyze PDF documents with AI assistance,
    ask questions about PDF content, or get intelligent summaries and insights.
    
    Usage: ai_pdf_analysis(file_path="path/to/document.pdf", query="What is the main topic?")
    
    Example:
    ai_pdf_analysis(file_path="documents/report.pdf", query="Summarize the key findings")
    
    Returns a string with AI-generated analysis of the PDF content.
    """
    
    inputs = {
        "file_path": {
            "type": "string",
            "description": "Path to the PDF file to analyze (filename or relative path)"
        },
        "query": {
            "type": "string", 
            "description": "Question or request about the PDF content"
        }
    }
    
    output_type = "string"
    
    def __init__(self, session_id: str = None):
        """Initialize AI PDF tool with optional session context"""
        super().__init__()
        self.session_id = session_id
    
    def _resolve_file_path(self, file_path: str) -> str:
        """
        Resolve file path to actual storage location.
        
        Args:
            file_path (str): Input file path (could be filename or relative path)
            
        Returns:
            str: Absolute path to the file
        """
        # If file_path is already absolute and exists, use it directly
        if os.path.isabs(file_path) and os.path.exists(file_path):
            return file_path
        
        # Try to find file in session storage if session_id is available
        if self.session_id:
            try:
                storage = SessionFileStorage(session_id=self.session_id)
                resolved_path = storage.path(file_path)
                if os.path.exists(resolved_path):
                    return resolved_path
            except Exception as e:
                logger.warning(f"Failed to resolve path via session storage: {str(e)}")
        
        # Try to find document by name in database
        try:
            # Look for document with this filename in any session
            document = Document.objects.filter(
                original_name=file_path,
                status='ready'
            ).first()
            
            if document:
                session_key = document.session.session.session_key
                storage = SessionFileStorage(session_id=session_key)
                resolved_path = storage.path(document.file_path)
                if os.path.exists(resolved_path):
                    return resolved_path
        except Exception as e:
            logger.warning(f"Failed to resolve path via database lookup: {str(e)}")
        
        # Return original path as fallback
        return file_path
    
    def forward(self, file_path: str, query: str) -> str:
        """
        Extract text from a PDF file and query it using AI through OpenRouter API.
        
        Args:
            file_path (str): Path to the PDF file
            query (str): Question or request about the PDF content
            
        Returns:
            str: AI response based on the PDF content and query
        """
        
        try:
            # Get API key from environment
            api_key = config('OPENROUTER_API_KEY', default=None)
            
            if not api_key:
                return "Error: OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable."
            
            # Resolve the actual file path
            resolved_path = self._resolve_file_path(file_path)
            logger.info(f"AI PDF Analysis: {file_path} -> {resolved_path}")
            
            # Check if PDF file exists
            if not os.path.exists(resolved_path):
                return f"Error: PDF file not found: {resolved_path}"
            
            # Extract text from PDF
            pdf_text = self._extract_pdf_text(resolved_path)
            
            if not pdf_text.strip():
                return "Error: No text could be extracted from the PDF file."
            
            # Prepare AI prompt
            prompt = self._create_ai_prompt(pdf_text, query)
            
            # Query the AI
            response = self._query_openrouter_ai(prompt, api_key)
            
            return response
            
        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            return f"Error: {str(e)}"
        except ValueError as e:
            logger.error(f"Value error: {str(e)}")
            return f"Error: {str(e)}"
        except Exception as e:
            logger.error(f"Error in AI PDF analysis: {str(e)}")
            return f"Error processing request: {str(e)}"

    def _extract_pdf_text(self, pdf_path: str) -> str:
        """
        Extract text content from a PDF file using PyMuPDF.
        
        Args:
            pdf_path (str): Path to the PDF file
            
        Returns:
            str: Extracted text content
        """
        try:
            doc = fitz.open(pdf_path)
            text_content = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_content += f"\n--- Page {page_num + 1} ---\n"
                text_content += page.get_text()
            
            doc.close()
            return text_content
            
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")

    def _create_ai_prompt(self, pdf_text: str, user_query: str) -> str:
        """
        Create an optimized prompt for the AI to analyze PDF content.
        
        Args:
            pdf_text (str): Extracted text from the PDF
            user_query (str): User's question or request
            
        Returns:
            str: Formatted prompt for the AI
        """
        
        preprompt = """You are an expert document analyst with exceptional reading comprehension skills. Your task is to carefully analyze the provided PDF document content and answer questions about it with precision and clarity.

INSTRUCTIONS:
- Read and understand the entire document content thoroughly
- Provide accurate, evidence-based answers using only information from the document
- If information is not available in the document, clearly state this
- Quote relevant sections when appropriate to support your answers
- Maintain objectivity and avoid making assumptions beyond what's written
- Structure your response clearly and concisely

DOCUMENT CONTENT:
"""
        
        user_prompt = f"\n\nUSER QUESTION: {user_query}\n\nPlease provide a comprehensive answer based on the document content above."
        
        return preprompt + pdf_text + user_prompt

    def _query_openrouter_ai(self, prompt: str, api_key: str) -> str:
        """
        Send query to OpenRouter API using Gemini 2.5 Flash model.
        
        Args:
            prompt (str): The complete prompt to send to the AI
            api_key (str): OpenRouter API key
            
        Returns:
            str: AI response
        """
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "google/gemini-2.5-flash-lite",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000000,
            "temperature": 0.1
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                return "Error: No response received from AI service."
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected API response format: {str(e)}")