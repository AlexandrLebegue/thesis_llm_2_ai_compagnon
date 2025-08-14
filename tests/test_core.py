import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from django.test import TestCase
import pandas as pd
import matplotlib.pyplot as plt
from tests.conftest import BaseTestCase, TestFileGenerator

# Import modules to test
from apps.documents.parsers.pdf_parser import PDFParser, PDFContent
from apps.documents.parsers.excel_parser import ExcelParser, ExcelContent
from apps.documents.parsers.word_parser import WordParser, WordContent
from apps.agents.tools.chart_generator import ChartGenerator
from apps.agents.tools.excel_modifier import ExcelModifier
from apps.agents.tools.word_modifier import WordModifier
from apps.agents.registry import ToolRegistry, ToolDefinition
from apps.agents.orchestrator import ChatbotOrchestrator


class TestDocumentParsers(BaseTestCase):
    """Test document parsing functionality"""
    
    def setUp(self):
        super().setUp()
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('pdfplumber.open')
    @patch('PyPDF2.PdfReader')
    def test_pdf_parser_success(self, mock_pdf_reader, mock_pdfplumber):
        """Test successful PDF parsing"""
        # Mock pdfplumber
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Sample PDF text content"
        mock_page.extract_tables.return_value = [
            [['Header1', 'Header2'], ['Cell1', 'Cell2']]
        ]
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf
        
        # Mock PyPDF2
        mock_reader = MagicMock()
        mock_reader.metadata = {
            '/Title': 'Test PDF',
            '/Author': 'Test Author',
            '/CreationDate': 'D:20240101000000'
        }
        mock_pdf_reader.return_value = mock_reader
        
        # Test parsing
        test_file = self.test_dir / "test.pdf"
        test_file.touch()
        
        result = PDFParser.parse(str(test_file))
        
        self.assertIsInstance(result, PDFContent)
        self.assertEqual(result.text, "Sample PDF text content")
        self.assertEqual(len(result.tables), 1)
        self.assertEqual(result.metadata['title'], 'Test PDF')
        self.assertEqual(result.page_count, 1)
    
    @patch('pdfplumber.open')
    def test_pdf_parser_failure(self, mock_pdfplumber):
        """Test PDF parser error handling"""
        mock_pdfplumber.side_effect = Exception("PDF read error")
        
        test_file = self.test_dir / "corrupted.pdf"
        test_file.touch()
        
        with self.assertRaises(Exception):
            PDFParser.parse(str(test_file))
    
    def test_pdf_generate_summary(self):
        """Test PDF summary generation"""
        content = PDFContent(
            text="This is a sample PDF with lots of content that should be summarized properly",
            tables=[],
            metadata={'title': 'Test Document', 'pages': 5},
            page_count=5
        )
        
        summary = PDFParser.generate_summary(content)
        
        self.assertIn('5 pages', summary)
        self.assertIn('Test Document', summary)
        self.assertLessEqual(len(summary), 500)
    
    @patch('pandas.ExcelFile')
    def test_excel_parser_success(self, mock_excel_file):
        """Test successful Excel parsing"""
        # Mock pandas ExcelFile
        mock_df1 = pd.DataFrame({
            'Column1': [1, 2, 3],
            'Column2': ['A', 'B', 'C']
        })
        mock_df2 = pd.DataFrame({
            'Value': [10, 20, 30]
        })
        
        mock_file = MagicMock()
        mock_file.sheet_names = ['Sheet1', 'Sheet2']
        mock_excel_file.return_value = mock_file
        
        with patch('pandas.read_excel') as mock_read_excel:
            mock_read_excel.side_effect = [mock_df1, mock_df2]
            
            test_file = self.test_dir / "test.xlsx"
            test_file.touch()
            
            result = ExcelParser.parse(str(test_file))
            
            self.assertIsInstance(result, ExcelContent)
            self.assertEqual(len(result.sheets), 2)
            self.assertEqual(result.metadata['sheet_count'], 2)
            self.assertEqual(result.metadata['total_rows'], 6)  # 3 + 3 rows
            self.assertIn('Sheet1', result.summary_stats)
    
    @patch('pandas.ExcelFile')
    def test_excel_parser_failure(self, mock_excel_file):
        """Test Excel parser error handling"""
        mock_excel_file.side_effect = Exception("Excel read error")
        
        test_file = self.test_dir / "corrupted.xlsx"
        test_file.touch()
        
        with self.assertRaises(Exception):
            ExcelParser.parse(str(test_file))
    
    def test_excel_generate_summary(self):
        """Test Excel summary generation"""
        sheets = {
            'Sheet1': pd.DataFrame({'A': [1, 2], 'B': [3, 4]}),
            'Sheet2': pd.DataFrame({'X': [5, 6], 'Y': [7, 8]})
        }
        content = ExcelContent(
            sheets=sheets,
            metadata={'sheet_count': 2, 'total_rows': 4},
            summary_stats={}
        )
        
        summary = ExcelParser.generate_summary(content)
        
        self.assertIn('2 sheets', summary)
        self.assertIn('4 total rows', summary)
        self.assertLessEqual(len(summary), 500)
    
    @patch('docx.Document')
    def test_word_parser_success(self, mock_document):
        """Test successful Word parsing"""
        # Mock docx Document
        mock_para1 = MagicMock()
        mock_para1.text = "This is a paragraph"
        mock_para1.style.name = "Normal"
        
        mock_para2 = MagicMock()
        mock_para2.text = "This is a heading"
        mock_para2.style.name = "Heading 1"
        
        mock_cell = MagicMock()
        mock_cell.text = "Cell content"
        mock_row = MagicMock()
        mock_row.cells = [mock_cell]
        mock_table = MagicMock()
        mock_table.rows = [mock_row]
        
        mock_core_props = MagicMock()
        mock_core_props.title = "Test Document"
        mock_core_props.author = "Test Author"
        mock_core_props.created = None
        mock_core_props.modified = None
        mock_core_props.subject = None
        
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2]
        mock_doc.tables = [mock_table]
        mock_doc.core_properties = mock_core_props
        mock_document.return_value = mock_doc
        
        test_file = self.test_dir / "test.docx"
        test_file.touch()
        
        result = WordParser.parse(str(test_file))
        
        self.assertIsInstance(result, WordContent)
        self.assertEqual(len(result.paragraphs), 2)
        self.assertEqual(len(result.headers), 1)
        self.assertEqual(len(result.tables), 1)
        self.assertEqual(result.metadata['title'], 'Test Document')
    
    @patch('docx.Document')
    def test_word_parser_failure(self, mock_document):
        """Test Word parser error handling"""
        mock_document.side_effect = Exception("Word read error")
        
        test_file = self.test_dir / "corrupted.docx"
        test_file.touch()
        
        with self.assertRaises(Exception):
            WordParser.parse(str(test_file))
    
    def test_word_generate_summary(self):
        """Test Word summary generation"""
        content = WordContent(
            paragraphs=["Para 1", "Para 2", "Para 3"],
            tables=[],
            headers=["Heading 1", "Heading 2"],
            metadata={
                'paragraph_count': 3,
                'word_count': 50,
                'title': 'Test Document'
            }
        )
        
        summary = WordParser.generate_summary(content)
        
        self.assertIn('3 paragraphs', summary)
        self.assertIn('50 words', summary)
        self.assertIn('Test Document', summary)
        self.assertLessEqual(len(summary), 500)


class TestChartGenerator(BaseTestCase):
    """Test chart generation functionality"""
    
    def setUp(self):
        super().setUp()
        self.output_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.output_dir, ignore_errors=True)
        plt.close('all')  # Close all matplotlib figures
    
    def test_generate_bar_chart(self):
        """Test bar chart generation"""
        data = {
            'x': ['A', 'B', 'C', 'D'],
            'y': [10, 20, 15, 25]
        }
        
        output_path = self.output_dir / "test_bar_chart.png"
        
        result_path = ChartGenerator.generate_chart(
            data=data,
            chart_type='bar',
            title='Test Bar Chart',
            xlabel='Categories',
            ylabel='Values',
            save_path=str(output_path)
        )
        
        self.assertEqual(result_path, str(output_path))
        self.assertTrue(Path(result_path).exists())
    
    def test_generate_line_chart(self):
        """Test line chart generation"""
        data = {
            'x': [1, 2, 3, 4, 5],
            'y': [10, 15, 13, 17, 20]
        }
        
        result_path = ChartGenerator.generate_chart(
            data=data,
            chart_type='line',
            title='Test Line Chart'
        )
        
        self.assertTrue(Path(result_path).exists())
    
    def test_generate_pie_chart(self):
        """Test pie chart generation"""
        data = {
            'x': ['Slice A', 'Slice B', 'Slice C'],
            'y': [30, 45, 25]
        }
        
        result_path = ChartGenerator.generate_chart(
            data=data,
            chart_type='pie',
            title='Test Pie Chart'
        )
        
        self.assertTrue(Path(result_path).exists())
    
    def test_unsupported_chart_type(self):
        """Test error handling for unsupported chart types"""
        data = {'x': [1, 2], 'y': [3, 4]}
        
        with self.assertRaises(ValueError) as context:
            ChartGenerator.generate_chart(data, chart_type='invalid')
        
        self.assertIn('Unsupported chart type', str(context.exception))
    
    def test_generate_from_dataframe(self):
        """Test chart generation from DataFrame"""
        df = pd.DataFrame({
            'Category': ['A', 'B', 'C'],
            'Value': [10, 20, 15]
        })
        
        result_path = ChartGenerator.generate_from_dataframe(
            df=df,
            chart_type='bar',
            x_column='Category',
            y_columns=['Value']
        )
        
        self.assertTrue(Path(result_path).exists())
    
    def test_generate_from_dataframe_auto_detect(self):
        """Test chart generation with auto-detected columns"""
        df = pd.DataFrame({
            'Value': [10, 20, 15, 25]
        })
        
        result_path = ChartGenerator.generate_from_dataframe(df, chart_type='line')
        
        self.assertTrue(Path(result_path).exists())


class TestExcelModifier(BaseTestCase):
    """Test Excel modification functionality"""
    
    def setUp(self):
        super().setUp()
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create a sample Excel file
        self.sample_file = self.test_dir / "sample.xlsx"
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': [4, 5, 6]
        })
        df.to_excel(self.sample_file, index=False)
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_modify_excel_add_sheet(self):
        """Test adding a new sheet to Excel file"""
        instructions = {
            'operations': [
                {'type': 'add_sheet', 'name': 'NewSheet'}
            ]
        }
        
        output_path = ExcelModifier.modify_excel(
            str(self.sample_file),
            instructions
        )
        
        self.assertTrue(Path(output_path).exists())
        
        # Verify the new sheet was added
        excel_file = pd.ExcelFile(output_path)
        self.assertIn('NewSheet', excel_file.sheet_names)
    
    def test_modify_excel_add_data(self):
        """Test adding data to existing sheet"""
        instructions = {
            'operations': [
                {
                    'type': 'add_data',
                    'sheet': 'Sheet1',
                    'data': [[7, 8], [9, 10]]
                }
            ]
        }
        
        output_path = ExcelModifier.modify_excel(
            str(self.sample_file),
            instructions
        )
        
        self.assertTrue(Path(output_path).exists())
        
        # Verify data was added
        df = pd.read_excel(output_path, sheet_name='Sheet1')
        self.assertEqual(len(df), 5)  # Original 3 + new 2 rows
    
    def test_modify_excel_add_formula(self):
        """Test adding formula to Excel file"""
        instructions = {
            'operations': [
                {
                    'type': 'add_formula',
                    'sheet': 'Sheet1',
                    'cell': 'C1',
                    'formula': '=SUM(A:A)'
                }
            ]
        }
        
        output_path = ExcelModifier.modify_excel(
            str(self.sample_file),
            instructions
        )
        
        self.assertTrue(Path(output_path).exists())
    
    def test_modify_excel_error_handling(self):
        """Test Excel modifier error handling"""
        with self.assertRaises(Exception):
            ExcelModifier.modify_excel(
                "nonexistent_file.xlsx",
                {'operations': []}
            )


class TestWordModifier(BaseTestCase):
    """Test Word modification functionality"""
    
    def setUp(self):
        super().setUp()
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('docx.Document')
    def test_modify_word_add_heading(self, mock_document_class):
        """Test adding heading to Word document"""
        # Create mock document
        mock_doc = MagicMock()
        mock_document_class.return_value = mock_doc
        
        instructions = {
            'operations': [
                {'type': 'add_heading', 'text': 'New Heading', 'level': 1}
            ]
        }
        
        output_path = WordModifier.modify_word(
            None,  # Create new document
            instructions
        )
        
        self.assertTrue(output_path)
        mock_doc.add_heading.assert_called_once_with('New Heading', level=1)
        mock_doc.save.assert_called_once()
    
    @patch('docx.Document')
    def test_modify_word_add_paragraph(self, mock_document_class):
        """Test adding paragraph to Word document"""
        mock_doc = MagicMock()
        mock_paragraph = MagicMock()
        mock_paragraph.runs = [MagicMock()]
        mock_doc.add_paragraph.return_value = mock_paragraph
        mock_document_class.return_value = mock_doc
        
        instructions = {
            'operations': [
                {
                    'type': 'add_paragraph',
                    'text': 'New paragraph',
                    'bold': True,
                    'italic': True
                }
            ]
        }
        
        output_path = WordModifier.modify_word(None, instructions)
        
        self.assertTrue(output_path)
        mock_doc.add_paragraph.assert_called_once_with('New paragraph')
        self.assertTrue(mock_paragraph.runs[0].bold)
        self.assertTrue(mock_paragraph.runs[0].italic)
    
    @patch('docx.Document')
    def test_modify_word_add_table(self, mock_document_class):
        """Test adding table to Word document"""
        mock_doc = MagicMock()
        mock_table = MagicMock()
        mock_table.rows = [MagicMock()]
        mock_table.add_row.return_value = MagicMock()
        mock_table.add_row.return_value.cells = [MagicMock(), MagicMock()]
        mock_doc.add_table.return_value = mock_table
        mock_document_class.return_value = mock_doc
        
        instructions = {
            'operations': [
                {
                    'type': 'add_table',
                    'data': [['Row1Col1', 'Row1Col2'], ['Row2Col1', 'Row2Col2']],
                    'headers': ['Header1', 'Header2']
                }
            ]
        }
        
        output_path = WordModifier.modify_word(None, instructions)
        
        self.assertTrue(output_path)
        mock_doc.add_table.assert_called_once()
    
    @patch('docx.Document')
    def test_modify_word_error_handling(self, mock_document_class):
        """Test Word modifier error handling"""
        mock_document_class.side_effect = Exception("Document error")
        
        with self.assertRaises(Exception):
            WordModifier.modify_word(None, {'operations': []})


class TestToolRegistry(BaseTestCase):
    """Test SmolAgents tool registry"""
    
    def setUp(self):
        super().setUp()
        self.registry = ToolRegistry()
    
    def test_register_tool(self):
        """Test tool registration"""
        @self.registry.register("test_tool", "A test tool")
        def test_function(param1: str, param2: int = 10) -> str:
            """Test function"""
            return f"{param1}_{param2}"
        
        self.assertIn("test_tool", self.registry.tools)
        tool_def = self.registry.get_tool("test_tool")
        
        self.assertEqual(tool_def.name, "test_tool")
        self.assertEqual(tool_def.description, "A test tool")
        self.assertIn("param1", tool_def.parameters)
        self.assertIn("param2", tool_def.parameters)
        self.assertTrue(tool_def.parameters["param1"]["required"])
        self.assertFalse(tool_def.parameters["param2"]["required"])
    
    def test_execute_tool(self):
        """Test tool execution"""
        @self.registry.register("add_numbers")
        def add_numbers(a: int, b: int) -> int:
            return a + b
        
        result = self.registry.execute_tool("add_numbers", a=5, b=3)
        self.assertEqual(result, 8)
    
    def test_execute_nonexistent_tool(self):
        """Test executing non-existent tool"""
        with self.assertRaises(ValueError):
            self.registry.execute_tool("nonexistent")
    
    def test_execute_tool_missing_required_param(self):
        """Test executing tool with missing required parameter"""
        @self.registry.register("test_required")
        def test_required(required_param: str) -> str:
            return required_param
        
        with self.assertRaises(ValueError):
            self.registry.execute_tool("test_required")
    
    def test_list_tools(self):
        """Test listing registered tools"""
        @self.registry.register("tool1")
        def tool1():
            pass
        
        @self.registry.register("tool2")
        def tool2():
            pass
        
        tools = self.registry.list_tools()
        self.assertIn("tool1", tools)
        self.assertIn("tool2", tools)


class TestChatbotOrchestrator(BaseTestCase):
    """Test SmolAgents orchestrator"""
    
    def setUp(self):
        super().setUp()
        self.mock_agent = MagicMock()
        self.mock_model = MagicMock()
    
    @patch('apps.agents.orchestrator.InferenceClientModel')
    @patch('apps.agents.orchestrator.ToolCallingAgent')
    @patch('apps.agents.registry.tool_registry')
    def test_orchestrator_initialization(self, mock_registry, mock_agent_class, mock_model_class):
        """Test orchestrator initialization"""
        mock_registry.tools = {}
        mock_agent_class.return_value = self.mock_agent
        mock_model_class.return_value = self.mock_model
        
        orchestrator = ChatbotOrchestrator()
        
        self.assertIsNotNone(orchestrator.model)
        self.assertIsNotNone(orchestrator.agent)
        mock_model_class.assert_called_once()
        mock_agent_class.assert_called_once()
    
    @patch('apps.agents.orchestrator.InferenceClientModel')
    @patch('apps.agents.orchestrator.ToolCallingAgent')
    @patch('apps.agents.registry.tool_registry')
    def test_process_request_success(self, mock_registry, mock_agent_class, mock_model_class):
        """Test successful request processing"""
        mock_registry.tools = {}
        mock_agent_class.return_value = self.mock_agent
        mock_model_class.return_value = self.mock_model
        
        self.mock_agent.run.return_value = "Test response"
        
        orchestrator = ChatbotOrchestrator()
        context = {
            'documents': [
                {'name': 'doc1.pdf', 'type': 'pdf', 'summary': 'Test document'}
            ]
        }
        
        result = orchestrator.process_request(
            instruction="Test instruction",
            context=context,
            session_id="test_session"
        )
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['result'], 'Test response')
        self.mock_agent.run.assert_called_once()
    
    @patch('apps.agents.orchestrator.InferenceClientModel')
    @patch('apps.agents.orchestrator.ToolCallingAgent')
    @patch('apps.agents.registry.tool_registry')
    def test_process_request_error(self, mock_registry, mock_agent_class, mock_model_class):
        """Test request processing with error"""
        mock_registry.tools = {}
        mock_agent_class.return_value = self.mock_agent
        mock_model_class.return_value = self.mock_model
        
        self.mock_agent.run.side_effect = Exception("Processing error")
        
        orchestrator = ChatbotOrchestrator()
        
        result = orchestrator.process_request(
            instruction="Test instruction",
            context={},
            session_id="test_session"
        )
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('Processing error', result['error'])
    
    @patch('apps.agents.orchestrator.InferenceClientModel')
    @patch('apps.agents.orchestrator.ToolCallingAgent')
    @patch('apps.agents.registry.tool_registry')
    def test_build_prompt(self, mock_registry, mock_agent_class, mock_model_class):
        """Test prompt building with context"""
        mock_registry.tools = {}
        mock_agent_class.return_value = self.mock_agent
        mock_model_class.return_value = self.mock_model
        
        orchestrator = ChatbotOrchestrator()
        context = {
            'documents': [
                {'name': 'doc1.pdf', 'type': 'pdf', 'summary': 'Test document 1'},
                {'name': 'doc2.xlsx', 'type': 'xlsx', 'summary': 'Test document 2'}
            ]
        }
        
        prompt = orchestrator._build_prompt("Generate a chart", context)
        
        self.assertIn("Available documents:", prompt)
        self.assertIn("doc1.pdf", prompt)
        self.assertIn("doc2.xlsx", prompt)
        self.assertIn("Generate a chart", prompt)
    
    @patch('apps.agents.orchestrator.InferenceClientModel')
    @patch('apps.agents.orchestrator.ToolCallingAgent')
    @patch('apps.agents.registry.tool_registry')
    def test_extract_artifacts(self, mock_registry, mock_agent_class, mock_model_class):
        """Test artifact extraction from results"""
        mock_registry.tools = {}
        mock_agent_class.return_value = self.mock_agent
        mock_model_class.return_value = self.mock_model
        
        orchestrator = ChatbotOrchestrator()
        
        # Test with chart result
        result = {
            'chart_path': '/tmp/test_chart.png',
            'name': 'Test Chart'
        }
        artifacts = orchestrator._extract_artifacts(result)
        
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]['type'], 'chart')
        self.assertEqual(artifacts[0]['path'], '/tmp/test_chart.png')
        
        # Test with multiple artifacts
        result = {
            'output_path': '/tmp/output.xlsx',
            'chart_path': '/tmp/chart.png',
            'artifact_path': '/tmp/artifact.pdf'
        }
        artifacts = orchestrator._extract_artifacts(result)
        
        self.assertEqual(len(artifacts), 3)


class TestDocumentSummarizer(BaseTestCase):
    """Test document summarization system"""
    
    def setUp(self):
        super().setUp()
        # Create a mock summarizer since the actual implementation
        # would depend on the specific summarization library used
        
    def test_pdf_summarization(self):
        """Test PDF document summarization"""
        content = PDFContent(
            text="This is a long PDF document with lots of important information about business processes and analytics data.",
            tables=[],
            metadata={'title': 'Business Report', 'pages': 10},
            page_count=10
        )
        
        summary = PDFParser.generate_summary(content, max_length=100)
        
        self.assertIsInstance(summary, str)
        self.assertLessEqual(len(summary), 100)
        self.assertIn('Business Report', summary)
    
    def test_excel_summarization(self):
        """Test Excel document summarization"""
        sheets = {
            'Sales': pd.DataFrame({'Product': ['A', 'B'], 'Revenue': [1000, 2000]}),
            'Costs': pd.DataFrame({'Category': ['Labor', 'Materials'], 'Amount': [500, 300]})
        }
        content = ExcelContent(
            sheets=sheets,
            metadata={'sheet_count': 2, 'total_rows': 4},
            summary_stats={'Sales': {'numeric_columns': ['Revenue']}}
        )
        
        summary = ExcelParser.generate_summary(content, max_length=200)
        
        self.assertIsInstance(summary, str)
        self.assertLessEqual(len(summary), 200)
        self.assertIn('2 sheets', summary)
    
    def test_word_summarization(self):
        """Test Word document summarization"""
        content = WordContent(
            paragraphs=["Introduction paragraph", "Analysis section", "Conclusion"],
            tables=[],
            headers=["Introduction", "Analysis", "Conclusion"],
            metadata={
                'paragraph_count': 3,
                'word_count': 150,
                'title': 'Research Paper'
            }
        )
        
        summary = WordParser.generate_summary(content, max_length=150)
        
        self.assertIsInstance(summary, str)
        self.assertLessEqual(len(summary), 150)
        self.assertIn('Research Paper', summary)


class TestCoreIntegration(BaseTestCase):
    """Test integration between core components"""
    
    def setUp(self):
        super().setUp()
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        plt.close('all')
    
    @patch('apps.documents.parsers.excel_parser.pd.ExcelFile')
    @patch('pandas.read_excel')
    def test_excel_to_chart_workflow(self, mock_read_excel, mock_excel_file):
        """Test complete workflow from Excel parsing to chart generation"""
        # Mock Excel data
        mock_df = pd.DataFrame({
            'Month': ['Jan', 'Feb', 'Mar'],
            'Sales': [100, 150, 120]
        })
        
        mock_file = MagicMock()
        mock_file.sheet_names = ['Sales Data']
        mock_excel_file.return_value = mock_file
        mock_read_excel.return_value = mock_df
        
        # Parse Excel
        test_file = self.test_dir / "sales.xlsx"
        test_file.touch()
        
        excel_content = ExcelParser.parse(str(test_file))
        
        # Generate chart from parsed data
        sales_data = excel_content.sheets['Sales Data']
        chart_data = {
            'x': sales_data['Month'].tolist(),
            'y': sales_data['Sales'].tolist()
        }
        
        chart_path = ChartGenerator.generate_chart(
            data=chart_data,
            chart_type='bar',
            title='Monthly


class TestCoreIntegration(BaseTestCase):
    """Test integration between core components"""
    
    def setUp(self):
        super().setUp()
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        plt.close('all')
    
    @patch('apps.documents.parsers.excel_parser.pd.ExcelFile')
    @patch('pandas.read_excel')
    def test_excel_to_chart_workflow(self, mock_read_excel, mock_excel_file):
        """Test complete workflow from Excel parsing to chart generation"""
        # Mock Excel data
        mock_df = pd.DataFrame({
            'Month': ['Jan', 'Feb', 'Mar'],
            'Sales': [100, 150, 120]
        })
        
        mock_file = MagicMock()
        mock_file.sheet_names = ['Sales Data']
        mock_excel_file.return_value = mock_file
        mock_read_excel.return_value = mock_df
        
        # Parse Excel
        test_file = self.test_dir / "sales.xlsx"
        test_file.touch()
        
        excel_content = ExcelParser.parse(str(test_file))
        
        # Generate chart from parsed data
        sales_data = excel_content.sheets['Sales Data']
        chart_data = {
            'x': sales_data['Month'].tolist(),
            'y': sales_data['Sales'].tolist()
        }
        
        chart_path = ChartGenerator.generate_chart(
            data=chart_data,
            chart_type='bar',
            title='Monthly Sales',
            xlabel='Month',
            ylabel='Sales ($)'
        )
        
        self.assertTrue(Path(chart_path).exists())
        self.assertIn('chart_', chart_path)
    
    @patch('apps.documents.parsers.pdf_parser.pdfplumber.open')
    @patch('apps.documents.parsers.pdf_parser.PyPDF2.PdfReader')
    def test_pdf_to_summary_workflow(self, mock_pdf_reader, mock_pdfplumber):
        """Test complete workflow from PDF parsing to summarization"""
        # Mock PDF parsing
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Quarterly financial report showing increased revenue and market expansion across multiple sectors."
        mock_page.extract_tables.return_value = []
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.return_value.__enter__.return_value = mock_pdf
        
        mock_reader = MagicMock()
        mock_reader.metadata = {'/Title': 'Q1 Financial Report'}
        mock_pdf_reader.return_value = mock_reader
        
        # Parse PDF
        test_file = self.test_dir / "report.pdf"
        test_file.touch()
        
        pdf_content = PDFParser.parse(str(test_file))
        
        # Generate summary
        summary = PDFParser.generate_summary(pdf_content, max_length=200)
        
        self.assertIn('Q1 Financial Report', summary)
        self.assertIn('1 pages', summary)
        self.assertLessEqual(len(summary), 200)


class TestEdgeCases(BaseTestCase):
    """Test edge cases and boundary conditions"""
    
    def setUp(self):
        super().setUp()
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.test_dir, ignore_errors=True)
        plt.close('all')
    
    def test_empty_data_handling(self):
        """Test handling of empty or minimal data"""
        # Test PDF with no text
        content = PDFContent(
            text="",
            tables=[],
            metadata={},
            page_count=0
        )
        summary = PDFParser.generate_summary(content)
        self.assertIsInstance(summary, str)
        
        # Test Excel with empty sheets
        empty_sheets = {'Empty': pd.DataFrame()}
        excel_content = ExcelContent(
            sheets=empty_sheets,
            metadata={'sheet_count': 1, 'total_rows': 0},
            summary_stats={}
        )
        summary = ExcelParser.generate_summary(excel_content)
        self.assertIsInstance(summary, str)
    
    def test_special_characters_handling(self):
        """Test handling of special characters in content"""
        # Test PDF with special characters
        content = PDFContent(
            text="Document with special chars: àáâãäåæçèéêë ñò Ω∑π",
            tables=[],
            metadata={'title': 'Special Chars Document™'},
            page_count=1
        )
        
        summary = PDFParser.generate_summary(content)
        self.assertIsInstance(summary, str)
        
        # Test chart with special character labels
        chart_data = {
            'x': ['Category A™', 'Category B®', 'Category C©'],
            'y': [10, 20, 15]
        }
        
        result_path = ChartGenerator.generate_chart(
            data=chart_data,
            chart_type='bar',
            title='Chart with Special™ Characters'
        )
        
        self.assertTrue(Path(result_path).exists())
    
    def test_large_data_simulation(self):
        """Test handling of large data structures"""
        # Create large DataFrame
        large_df = pd.DataFrame({
            'x': list(range(1000)),
            'y': [i * 2 for i in range(1000)]
        })
        
        # Test chart generation with large dataset
        chart_data = {
            'x': large_df['x'].tolist()[:100],  # Limit for performance
            'y': large_df['y'].tolist()[:100]
        }
        
        result_path = ChartGenerator.generate_chart(
            data=chart_data,
            chart_type='line'
        )
        
        self.assertTrue(Path(result_path).exists())
    
    def test_error_propagation_workflow(self):
        """Test error handling across integrated components"""
        # Test chart generation with invalid data
        with self.assertRaises(Exception):
            ChartGenerator.generate_chart(
                data={'x': [], 'y': []},  # Empty data
                chart_type='bar'
            )
        
        # Test Excel modification with invalid file
        with self.assertRaises(Exception):
            ExcelModifier.modify_excel(
                "nonexistent.xlsx",
                {'operations': []}
            )
        
        # Test registry with missing parameters
        registry = ToolRegistry()
        
        @registry.register("test_strict")
        def test_strict(required_param: str) -> str:
            return required_param
        
        with self.assertRaises(ValueError):
            registry.execute_tool("test_strict")  # Missing required parameter


if __name__ == '__main__':
    import unittest
    unittest.main()