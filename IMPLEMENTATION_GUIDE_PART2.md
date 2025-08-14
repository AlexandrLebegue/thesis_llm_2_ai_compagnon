# Ultra PDF Chatbot 3000 - Implementation Guide (Part 2)

## 6. Chart Generation Tool (continued)

```python
# apps/agents/tools/chart_generator.py (continued)
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
                save_path = Path('/tmp/ultra_pdf_chatbot/charts') / f"chart_{uuid.uuid4().hex}.png"
                save_path.parent.mkdir(parents=True, exist_ok=True)
            
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
```

## 7. Document Modification Tools

### 7.1 Excel Modifier with Charts
```python
# apps/agents/tools/excel_modifier.py
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
        
        Instructions format:
        {
            'operations': [
                {'type': 'add_sheet', 'name': 'NewSheet'},
                {'type': 'add_data', 'sheet': 'Sheet1', 'data': [[...]], 'start_cell': 'A1'},
                {'type': 'add_chart', 'sheet': 'Sheet1', 'chart_type': 'column', 'data_range': 'A1:B10'},
                {'type': 'add_formula', 'sheet': 'Sheet1', 'cell': 'C1', 'formula': '=SUM(A:A)'},
            ]
        }
        """
        try:
            # Read existing Excel file
            excel_file = pd.ExcelFile(file_path)
            sheets = {name: pd.read_excel(excel_file, sheet_name=name) 
                     for name in excel_file.sheet_names}
            
            # Generate output path
            if not output_path:
                output_path = Path('/tmp/ultra_pdf_chatbot/outputs') / f"modified_{Path(file_path).name}"
                output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create new workbook with XlsxWriter
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Write existing sheets
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Process operations
                for operation in instructions.get('operations', []):
                    op_type = operation['type']
                    
                    if op_type == 'add_sheet':
                        worksheet = workbook.add_worksheet(operation['name'])
                        
                    elif op_type == 'add_data':
                        sheet_name = operation['sheet']
                        if sheet_name in sheets:
                            df = sheets[sheet_name]
                            new_data = pd.DataFrame(operation['data'])
                            df = pd.concat([df, new_data], ignore_index=True)
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    elif op_type == 'add_chart':
                        ExcelModifier._add_chart(
                            workbook, 
                            writer.sheets[operation['sheet']],
                            operation
                        )
                    
                    elif op_type == 'add_formula':
                        worksheet = writer.sheets[operation['sheet']]
                        worksheet.write_formula(operation['cell'], operation['formula'])
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error modifying Excel: {str(e)}")
            raise
    
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
```

### 7.2 Word Modifier
```python
# apps/agents/tools/word_modifier.py
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from PIL import Image
import io

logger = logging.getLogger(__name__)

class WordModifier:
    """Modify Word documents and insert images/charts"""
    
    @staticmethod
    def modify_word(
        file_path: str,
        instructions: Dict[str, Any],
        images: List[str] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Modify Word document based on instructions
        
        Instructions format:
        {
            'operations': [
                {'type': 'add_heading', 'text': 'New Section', 'level': 1},
                {'type': 'add_paragraph', 'text': 'Some text...'},
                {'type': 'add_table', 'data': [[...]], 'headers': [...]},
                {'type': 'insert_image', 'image_index': 0, 'width': 6},
                {'type': 'add_page_break'},
            ]
        }
        """
        try:
            # Open existing document or create new
            if file_path and Path(file_path).exists():
                doc = Document(file_path)
            else:
                doc = Document()
            
            # Process operations
            for operation in instructions.get('operations', []):
                op_type = operation['type']
                
                if op_type == 'add_heading':
                    doc.add_heading(operation['text'], level=operation.get('level', 1))
                
                elif op_type == 'add_paragraph':
                    paragraph = doc.add_paragraph(operation['text'])
                    if operation.get('bold'):
                        paragraph.runs[0].bold = True
                    if operation.get('italic'):
                        paragraph.runs[0].italic = True
                    if operation.get('alignment'):
                        alignment_map = {
                            'center': WD_ALIGN_PARAGRAPH.CENTER,
                            'right': WD_ALIGN_PARAGRAPH.RIGHT,
                            'justify': WD_ALIGN_PARAGRAPH.JUSTIFY,
                        }
                        paragraph.alignment = alignment_map.get(operation['alignment'])
                
                elif op_type == 'add_table':
                    WordModifier._add_table(doc, operation)
                
                elif op_type == 'insert_image' and images:
                    image_index = operation.get('image_index', 0)
                    if image_index < len(images):
                        width = Inches(operation.get('width', 6))
                        doc.add_picture(images[image_index], width=width)
                
                elif op_type == 'add_page_break':
                    doc.add_page_break()
            
            # Save document
            if not output_path:
                output_path = Path('/tmp/ultra_pdf_chatbot/outputs') / f"modified_{Path(file_path).stem}.docx"
                output_path.parent.mkdir(parents=True, exist_ok=True)
            
            doc.save(output_path)
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error modifying Word document: {str(e)}")
            raise
    
    @staticmethod
    def _add_table(doc: Document, config: Dict[str, Any]):
        """Add table to document"""
        data = config['data']
        headers = config.get('headers', [])
        
        # Create table
        table = doc.add_table(rows=1 if headers else 0, cols=len(data[0]))
        table.style = 'Table Grid'
        
        # Add headers
        if headers:
            header_cells = table.rows[0].cells
            for i, header in enumerate(headers):
                header_cells[i].text = str(header)
                header_cells[i].paragraphs[0].runs[0].bold = True
        
        # Add data
        for row_data in data:
            row_cells = table.add_row().cells
            for i, cell_data in enumerate(row_data):
                row_cells[i].text = str(cell_data)
```

## 8. SmolAgents Integration

### 8.1 Tool Registry
```python
# apps/agents/registry.py
from typing import Dict, Callable, Any
import inspect
from dataclasses import dataclass

@dataclass
class ToolDefinition:
    name: str
    func: Callable
    description: str
    parameters: Dict[str, Any]
    returns: str

class ToolRegistry:
    """Registry for SmolAgents tools"""
    
    def __init__(self):
        self.tools = {}
    
    def register(self, name: str, description: str = None):
        """Decorator to register a tool"""
        def decorator(func):
            # Extract function signature
            sig = inspect.signature(func)
            parameters = {}
            
            for param_name, param in sig.parameters.items():
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else Any
                param_info = {
                    'type': param_type,
                    'required': param.default == inspect.Parameter.empty,
                    'default': param.default if param.default != inspect.Parameter.empty else None
                }
                parameters[param_name] = param_info
            
            # Create tool definition
            tool_def = ToolDefinition(
                name=name,
                func=func,
                description=description or func.__doc__ or '',
                parameters=parameters,
                returns=sig.return_annotation if sig.return_annotation != inspect.Signature.empty else Any
            )
            
            self.tools[name] = tool_def
            return func
        return decorator
    
    def get_tool(self, name: str) -> ToolDefinition:
        """Get tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tools"""
        return list(self.tools.keys())
    
    def execute_tool(self, name: str, **kwargs) -> Any:
        """Execute a tool with given parameters"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        
        # Validate parameters
        for param_name, param_info in tool.parameters.items():
            if param_info['required'] and param_name not in kwargs:
                raise ValueError(f"Required parameter '{param_name}' missing for tool '{name}'")
        
        return tool.func(**kwargs)

# Global registry instance
tool_registry = ToolRegistry()
```

### 8.2 SmolAgents Tools Implementation
```python
# apps/agents/tools/__init__.py
from apps.agents.registry import tool_registry
from apps.documents.parsers import PDFParser, ExcelParser, WordParser
from apps.agents.tools.chart_generator import ChartGenerator
from apps.agents.tools.excel_modifier import ExcelModifier
from apps.agents.tools.word_modifier import WordModifier
import pandas as pd
from pathlib import Path
import uuid
import logging

logger = logging.getLogger(__name__)

@tool_registry.register("parse_pdf", "Extract text and tables from PDF files")
def parse_pdf(file_path: str) -> Dict[str, Any]:
    """Parse PDF file and return structured content"""
    try:
        content = PDFParser.parse(file_path)
        return {
            'text': content.text,
            'tables': content.tables,
            'metadata': content.metadata,
            'summary': PDFParser.generate_summary(content)
        }
    except Exception as e:
        logger.error(f"Error in parse_pdf tool: {str(e)}")
        return {'error': str(e)}

@tool_registry.register("parse_excel", "Read and analyze Excel spreadsheets")
def parse_excel(file_path: str) -> Dict[str, Any]:
    """Parse Excel file and return data"""
    try:
        content = ExcelParser.parse(file_path)
        return {
            'sheets': {name: df.to_dict('records') for name, df in content.sheets.items()},
            'metadata': content.metadata,
            'summary': ExcelParser.generate_summary(content)
        }
    except Exception as e:
        logger.error(f"Error in parse_excel tool: {str(e)}")
        return {'error': str(e)}

@tool_registry.register("parse_word", "Extract content from Word documents")
def parse_word(file_path: str) -> Dict[str, Any]:
    """Parse Word document and return content"""
    try:
        content = WordParser.parse(file_path)
        return {
            'text': '\n'.join(content.paragraphs),
            'tables': content.tables,
            'headers': content.headers,
            'metadata': content.metadata,
            'summary': WordParser.generate_summary(content)
        }
    except Exception as e:
        logger.error(f"Error in parse_word tool: {str(e)}")
        return {'error': str(e)}

@tool_registry.register("modify_excel", "Modify Excel files and add charts")
def modify_excel(file_path: str, instructions: Dict[str, Any]) -> Dict[str, str]:
    """Modify Excel file based on instructions"""
    try:
        output_path = ExcelModifier.modify_excel(file_path, instructions)
        return {'output_path': output_path, 'status': 'success'}
    except Exception as e:
        logger.error(f"Error in modify_excel tool: {str(e)}")
        return {'error': str(e), 'status': 'failed'}

@tool_registry.register("modify_word", "Modify Word documents and insert content")
def modify_word(file_path: str, instructions: Dict[str, Any], images: List[str] = None) -> Dict[str, str]:
    """Modify Word document based on instructions"""
    try:
        output_path = WordModifier.modify_word(file_path, instructions, images)
        return {'output_path': output_path, 'status': 'success'}
    except Exception as e:
        logger.error(f"Error in modify_word tool: {str(e)}")
        return {'error': str(e), 'status': 'failed'}

@tool_registry.register("generate_chart", "Create charts from data")
def generate_chart(data_spec: Dict[str, Any]) -> Dict[str, str]:
    """Generate chart from data specification"""
    try:
        chart_path = ChartGenerator.generate_chart(
            data=data_spec.get('data'),
            chart_type=data_spec.get('type', 'bar'),
            title=data_spec.get('title', ''),
            xlabel=data_spec.get('xlabel', ''),
            ylabel=data_spec.get('ylabel', '')
        )
        return {'chart_path': chart_path, 'status': 'success'}
    except Exception as e:
        logger.error(f"Error in generate_chart tool: {str(e)}")
        return {'error': str(e), 'status': 'failed'}

@tool_registry.register("save_artifact", "Save generated content as downloadable file")
def save_artifact(content: Any, file_type: str) -> Dict[str, str]:
    """Save content as artifact for download"""
    try:
        artifact_id = uuid.uuid4().hex
        artifact_path = Path('/tmp/ultra_pdf_chatbot/artifacts') / f"{artifact_id}.{file_type}"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, bytes):
            artifact_path.write_bytes(content)
        elif isinstance(content, str):
            artifact_path.write_text(content)
        else:
            # Handle other types (DataFrame, etc.)
            if hasattr(content, 'to_csv'):
                content.to_csv(artifact_path)
            else:
                artifact_path.write_text(str(content))
        
        return {'artifact_id': artifact_id, 'path': str(artifact_path), 'status': 'success'}
    except Exception as e:
        logger.error(f"Error in save_artifact tool: {str(e)}")
        return {'error': str(e), 'status': 'failed'}
```

### 8.3 SmolAgents Orchestrator
```python
# apps/agents/orchestrator.py
from smolagents import Tool, Agent, HfApiModel
from apps.agents.registry import tool_registry
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ChatbotOrchestrator:
    """Orchestrate SmolAgents for document processing"""
    
    def __init__(self, model_name: str = "meta-llama/Llama-3.2-3B-Instruct"):
        self.model = HfApiModel(model_name)
        self.tools = self._create_smolagent_tools()
        self.agent = Agent(
            tools=self.tools,
            model=self.model,
            max_steps=10
        )
    
    def _create_smolagent_tools(self) -> List[Tool]:
        """Convert registry tools to SmolAgents tools"""
        smolagent_tools = []
        
        for tool_name, tool_def in tool_registry.tools.items():
            # Create SmolAgent tool wrapper
            class SmolAgentTool(Tool):
                name = tool_name
                description = tool_def.description
                inputs = {
                    param: param_info['type'].__name__ if hasattr(param_info['type'], '__name__') else 'Any'
                    for param, param_info in tool_def.parameters.items()
                }
                output_type = tool_def.returns.__name__ if hasattr(tool_def.returns, '__name__') else 'Any'
                
                def forward(self, **kwargs):
                    return tool_registry.execute_tool(tool_name, **kwargs)
            
            smolagent_tools.append(SmolAgentTool())
        
        return smolagent_tools
    
    def process_request(
        self,
        instruction: str,
        context: Dict[str, Any],
        session_id: str
    ) -> Dict[str, Any]:
        """Process user request with context"""
        
        try:
            # Build prompt with context
            prompt = self._build_prompt(instruction, context)
            
            # Run agent
            result = self.agent.run(prompt)
            
            # Process results
            return {
                'status': 'success',
                'result': result,
                'artifacts': self._extract_artifacts(result)
            }
            
        except Exception as e:
            logger.error(f"Error in orchestrator: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _build_prompt(self, instruction: str, context: Dict[str, Any]) -> str:
        """Build prompt with document context"""
        prompt_parts = []
        
        # Add document context
        if context.get('documents'):
            prompt_parts.append("Available documents:")
            for doc in context['documents']:
                prompt_parts.append(f"- {doc['name']} ({doc['type']}): {doc['summary']}")
        
        # Add instruction
        prompt_parts.append(f"\nUser request: {instruction}")
        
        return '\n'.join(prompt_parts)
    
    def _extract_artifacts(self, result: Any) -> List[Dict[str, str]]:
        """Extract generated artifacts from result"""
        artifacts = []
        
        # Parse result for file paths and artifact IDs
        # This depends on the structure of SmolAgents results
        
        return artifacts
```

## 9. Django Views and Templates

### 9.1 Main Chat View
```python
# apps/chat/views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sessions.models import Session
from django_htmx.http import HttpResponseClientRedirect
from apps.documents.models import DocumentSession, Document, DocumentContext
from apps.chat.models import Conversation, Message, Artifact
from apps.agents.orchestrator import ChatbotOrchestrator
from tasks.document_tasks import process_document_async
from tasks.agent_tasks import run_agent_task_async
from celery.result import AsyncResult
import json
import logging

logger = logging.getLogger(__name__)

class ChatView:
    """Main chat interface view"""
    
    @staticmethod
    def index(request):
        """Main chat page"""
        # Get or create document session
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        doc_session, created = DocumentSession.objects.get_or_create(
            session_id=session_key
        )
        
        # Get conversation
        conversation = Conversation.objects.filter(
            session=doc_session
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(session=doc_session)
        
        # Get documents and messages
        documents = doc_session.documents.all()
        messages = conversation.messages.all()
        
        context = {
            'documents': documents,
            'messages': messages,
            'max_documents': settings.MAX_DOCUMENTS_PER_SESSION,
            'current_document_count': documents.count(),
        }
        
        return render(request, 'chat/index.html', context)
    
    @staticmethod
    @require_http_methods(["POST"])
    def send_message(request):
        """Handle chat message submission"""
        try:
            # Get session and conversation
            doc_session = DocumentSession.objects.get(
                session_id=request.session.session_key
            )
            conversation = Conversation.objects.get(session=doc_session)
            
            # Get message and files
            message_text = request.POST.get('message', '')
            files = request.FILES.getlist('files')
            
            # Process uploaded files
            if files:
                for file in files:
                    # Check document limit
                    if doc_session.documents.count() >= settings.MAX_DOCUMENTS_PER_SESSION:
                        return JsonResponse({
                            'error': f'Maximum {settings.MAX_DOCUMENTS_PER_SESSION} documents allowed'
                        }, status=400)
                    
                    # Save document
                    document = Document.objects.create(
                        session=doc_session,
                        original_name=file.name,
                        file_size=file.size,
                        document_type=file.name.split('.')[-1]
                    )
                    
                    # Save file to temp storage
                    storage = SessionFileStorage(session_id=request.session.session_key)
                    file_path = storage.save(file.name, file)
                    document.file_path = file_path
                    document.save()
                    
                    # Queue processing
                    task = process_document_async.delay(document.id)
                    document.task_id = task.id
                    document.save()
            
            # Create user message
            user_message = Message.objects.create(
                conversation=conversation,
                role='user',
                content=message_text
            )
            
            # Get context
            context_obj, created = DocumentContext.objects.get_or_create(
                session=doc_session
            )
            context_obj.update_context()
            
            # Determine if async processing is needed
            use_async = ChatView._should_use_async(message_text, doc_session)
            
            if use_async:
                # Queue agent task
                task = run_agent_task_async.delay(
                    instruction=message_text,
                    context=context_obj.context_data,
                    session_id=request.session.session_key,
                    message_id=str(user_message.id)
                )
                
                # Create assistant message with task ID
                assistant_message = Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content='Processing your request...',
                    task_id=task.id,
                    task_status='PENDING'
                )
                
                # Return HTMX response with polling trigger
                return render(request, 'chat/partials/message_pending.html', {
                    'message': assistant_message
                })
            
            else:
                # Process synchronously
                orchestrator = ChatbotOrchestrator()
                result = orchestrator.process_request(
                    instruction=message_text,
                    context=context_obj.context_data,
                    session_id=request.session.session_key
                )
                
                # Create assistant message
                assistant_message = Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=result.get('result', 'I processed your request.'),
                    artifacts=result.get('artifacts', [])
                )
                
                # Save artifacts
                for artifact_data in result.get('artifacts', []):
                    Artifact.objects.create(
                        message=assistant_message,
                        **artifact_data
                    )
                
                # Return HTMX response
                return render(request, 'chat/partials/message.html', {
                    'message': assistant_message
                })
                
        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    @staticmethod
    def _should_use_async(message: str, session: DocumentSession) -> bool:
        """Determine if request should be processed asynchronously"""
        # Use async for:
        # - Multiple documents (>3)
        # - Large documents (total > 10MB)
        # - Complex operations (modify, generate charts)
        
        doc_count = session.documents.count()
        total_size = session.documents.aggregate(
            total=models.Sum('file_size')
        )['total'] or 0
        
        complex_keywords = ['modify', 'generate', 'create chart', 'analyze all']
        has_complex = any(keyword in message.lower() for keyword in complex_keywords)
        
        return doc_count > 3 or total_size > 10*1024*1024 or has_complex
    
    @staticmethod
    @require_http_methods(["GET"])
    def check_task_status(request, task_id):
        """Check status of async task"""
        try:
            result = AsyncResult(task_id)
            
            if result.ready():
                message = Message.objects.get(task_id=task_id)
                
                if result.successful():
                    # Update message with result
                    task_result = result.get()
                    message.content = task_result.get('result', 'Task completed.')
                    message.artifacts = task_result.get('artifacts', [])
                    message.task_status = 'SUCCESS'
                    message.save()
                    
                    # Save artifacts
                    for artifact_data in task_result.get('artifacts', []):
                        Artifact.objects.create(
                            message=message,
                            **artifact_data
                        )
                else:
                    # Handle failure
                    message.content = f"Error: {result.info}"
                    message.task_status = 'FAILURE'
                    message.save()
                
                # Return completed message
                return render(request, 'chat/partials/message.html', {
                    'message': message
                })
            
            else:
                #