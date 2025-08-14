from smolagents import CodeAgent, InferenceClientModel, OpenAIServerModel
from typing import Dict, Any, List
import logging
import os
import mimetypes
import glob
import time
from pathlib import Path
from datetime import datetime, timedelta
from decouple import config

# Import all the SmolAgents tools
from apps.agents.tools.parse_pdf_tool import ParsePDFTool
from apps.agents.tools.parse_excel_tool import ParseExcelTool
from apps.agents.tools.parse_word_tool import ParseWordTool
from apps.agents.tools.modify_excel_tool import ModifyExcelTool
from apps.agents.tools.modify_word_tool import ModifyWordTool
from apps.agents.tools.generate_chart_tool import GenerateChartTool
from apps.agents.tools.save_artifact_tool import SaveArtifactTool
# from apps.agents.tools.excel_generator_tool import ExcelGeneratorTool
from apps.agents.tools.excel_generator import ExcelGeneratorTool
from apps.agents.tools.word_generator import SimpleWordGeneratorTool

# Import Django models (lazy import to avoid circular imports)
from django.utils import timezone

logger = logging.getLogger(__name__)

class ChatbotOrchestrator:
    """Orchestrate SmolAgents for document processing"""
    
    def __init__(self, model_name: str = "qwen/qwen3-coder", session_id: str = None):
        # Get OpenRouter API key from environment
        api_key = config('OPENROUTER_API_KEY', default=None)
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        
        # Initialize OpenRouter model (OpenAI-compatible API)
        self.model = OpenAIServerModel(
            api_base="https://openrouter.ai/api/v1",
            model_id=model_name,
            api_key=api_key,
            max_tokens=180000,  # Set max tokens to 262144 for better performance
        )
        
        # Store session_id
        self.session_id = session_id
        
        # Create tool instances directly
        self.tools = self._create_tools(session_id=session_id)
        
        # Initialize agent with tools
        self.agent = CodeAgent(
            tools=self.tools,
            model=self.model,
            max_steps=10,
            verbosity_level=1,
            additional_authorized_imports=[
                "pandas", "numpy", "json", "os", "tempfile", "random", "re",
                "datetime", "pathlib", "io", "base64", "requests"
            ]
        )
    
    def _create_tools(self, session_id: str = None) -> List:
        """Create instances of all SmolAgents tools"""
        return [
            ParsePDFTool(session_id=session_id),
            ParseExcelTool(session_id=session_id),
            ParseWordTool(session_id=session_id),
            ModifyExcelTool(),
            # ModifyWordTool(),
            SimpleWordGeneratorTool(),
            GenerateChartTool(),
            SaveArtifactTool(),
            ExcelGeneratorTool()
            # ExcelGeneratorTool()
        ]
    
    def process_request(
        self,
        instruction: str,
        context: Dict[str, Any],
        session_id: str,
        message=None
    ) -> Dict[str, Any]:
        """Process user request with context"""
        
        try:
            # Build prompt with context
            prompt = self._build_prompt(instruction, context)
            
            # Track temp directory state before agent execution
            temp_dir = os.path.join(os.getcwd(), 'temp')
            files_before = self._get_temp_files_snapshot(temp_dir)
            
            # Run agent with better error handling
            try:
                logger.debug(f"Running CodeAgent with prompt length: {len(prompt)}")
                result = self.agent.run(prompt)
                logger.debug(f"CodeAgent result type: {type(result)}")
                logger.debug(f"CodeAgent result preview: {str(result)[:500]}...")
                
                # Validate result
                if result is None:
                    logger.warning("Agent returned None result")
                    return {
                        'status': 'error',
                        'error': 'Agent returned no response'
                    }
                
                # Convert result to string if it's not already
                result_str = str(result) if result is not None else "No response generated"
                
                # Track temp directory state after agent execution
                files_after = self._get_temp_files_snapshot(temp_dir)
                
                # Extract artifacts from multiple sources
                artifacts = self._extract_artifacts_enhanced(result, files_before, files_after)
                
                # Create Artifact database records if message is provided
                if message and artifacts:
                    self._create_artifact_records(artifacts, message)
                
                # Process results
                return {
                    'status': 'success',
                    'result': result_str,
                    'artifacts': artifacts
                }
                
            except AttributeError as attr_error:
                # Handle token counting errors specifically
                if "prompt_tokens" in str(attr_error):
                    logger.warning(f"Token counting error (likely due to malformed response): {str(attr_error)}")
                    return {
                        'status': 'error',
                        'error': 'Response processing error - please try again with a simpler request'
                    }
                else:
                    raise attr_error
            except KeyError as key_error:
                # Handle tool parsing errors specifically
                if "tool_name_key" in str(key_error) or "'name' not found" in str(key_error):
                    logger.warning(f"Tool parsing error (likely due to malformed tool response): {str(key_error)}")
                    return {
                        'status': 'error',
                        'error': 'Tool response formatting error - the tool returned an unexpected format. Please try rephrasing your request.'
                    }
                else:
                    raise key_error
            except Exception as parse_error:
                # Handle any other parsing errors
                if "tool call" in str(parse_error).lower() or "parsing" in str(parse_error).lower():
                    logger.warning(f"Tool call parsing error: {str(parse_error)}")
                    return {
                        'status': 'error',
                        'error': 'Response parsing error - please try rephrasing your request with simpler instructions.'
                    }
                else:
                    raise parse_error
            
        except Exception as e:
            logger.error(f"Error in orchestrator: {str(e)}", exc_info=True)
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
    
    def _get_temp_files_snapshot(self, temp_dir: str) -> Dict[str, float]:
        """Get snapshot of temp directory files with modification times"""
        snapshot = {}
        if os.path.exists(temp_dir):
            try:
                # Get all files recursively in temp directory
                for pattern in ['**/*.xlsx', '**/*.docx', '**/*.png', '**/*.jpg', '**/*.jpeg',
                               '**/*.gif', '**/*.svg', '**/*.pdf', '**/*.txt', '**/*.csv']:
                    for file_path in glob.glob(os.path.join(temp_dir, pattern), recursive=True):
                        try:
                            mtime = os.path.getmtime(file_path)
                            snapshot[file_path] = mtime
                        except OSError:
                            continue
            except Exception as e:
                logger.warning(f"Error getting temp files snapshot: {e}")
        return snapshot
    
    def _extract_artifacts_enhanced(self, result: Any, files_before: Dict[str, float], files_after: Dict[str, float]) -> List[Dict[str, str]]:
        """Enhanced artifact extraction that combines multiple detection methods"""
        artifacts = []
        
        # Method 1: Traditional extraction from result content
        traditional_artifacts = self._extract_artifacts(result)
        artifacts.extend(traditional_artifacts)
        
        # Method 2: File system based detection
        fs_artifacts = self._extract_artifacts_from_filesystem(files_before, files_after)
        artifacts.extend(fs_artifacts)
        
        # Method 3: Enhanced string parsing for CodeAgent output
        if isinstance(result, str):
            code_artifacts = self._extract_artifacts_from_code_output(result)
            artifacts.extend(code_artifacts)
        
        # Remove duplicates while preserving order
        seen_paths = set()
        unique_artifacts = []
        for artifact in artifacts:
            path = artifact.get('path', '')
            if path and path not in seen_paths:
                seen_paths.add(path)
                unique_artifacts.append(artifact)
        
        logger.info(f"Enhanced artifact extraction found {len(unique_artifacts)} unique artifacts")
        return unique_artifacts
    
    def _extract_artifacts_from_filesystem(self, files_before: Dict[str, float], files_after: Dict[str, float]) -> List[Dict[str, str]]:
        """Extract artifacts by comparing filesystem state"""
        artifacts = []
        
        # Find new files created during agent execution
        new_files = set(files_after.keys()) - set(files_before.keys())
        
        # Find modified files (with newer modification times)
        modified_files = set()
        for file_path in files_before.keys():
            if file_path in files_after and files_after[file_path] > files_before[file_path]:
                modified_files.add(file_path)
        
        # Process new and modified files
        for file_path in new_files.union(modified_files):
            if Path(file_path).exists():
                artifacts.append({
                    'type': 'file',
                    'path': file_path,
                    'name': Path(file_path).name
                })
                logger.debug(f"Filesystem detection found: {Path(file_path).name}")
        
        return artifacts
    
    def _extract_artifacts_from_code_output(self, result_str: str) -> List[Dict[str, str]]:
        """Extract artifacts from CodeAgent string output with enhanced patterns"""
        artifacts = []
        
        # Enhanced patterns for CodeAgent output
        patterns = [
            # Function call patterns with file paths
            (r'excel_generator\([^)]*filename=["\']([^"\']+)["\']', 'file', 'Generated Excel File'),
            (r'simple_word_generator\([^)]*filename=["\']([^"\']+)["\']', 'file', 'Generated Word Document'),
            (r'generate_chart\([^)]*filename=["\']([^"\']+)["\']', 'chart', 'Generated Chart'),
            
            # Direct file path mentions
            (r'saved to[:\s]+([^\s\n]+\.xlsx)', 'file', 'Excel File'),
            (r'saved to[:\s]+([^\s\n]+\.docx)', 'file', 'Word Document'),
            (r'saved to[:\s]+([^\s\n]+\.png)', 'chart', 'Chart Image'),
            (r'created[:\s]+([^\s\n]+\.xlsx)', 'file', 'Excel File'),
            (r'created[:\s]+([^\s\n]+\.docx)', 'file', 'Word Document'),
            (r'generated[:\s]+([^\s\n]+\.png)', 'chart', 'Chart Image'),
            
            # Temp directory patterns
            (r'(temp[/\\][\w\\/.-]+\.xlsx)', 'file', 'Generated Excel File'),
            (r'(temp[/\\][\w\\/.-]+\.docx)', 'file', 'Generated Word Document'),
            (r'(temp[/\\][\w\\/.-]+\.png)', 'chart', 'Generated Chart'),
            (r'(temp[/\\][\w\\/.-]+\.jpg)', 'chart', 'Generated Chart'),
            (r'(temp[/\\][\w\\/.-]+\.svg)', 'chart', 'Generated Chart'),
        ]
        
        import re
        for pattern, file_type, default_name in patterns:
            matches = re.findall(pattern, result_str, re.IGNORECASE)
            for match in matches:
                # Clean up the path
                file_path = match.strip().strip('"\'')
                
                # Make path absolute if relative
                if not os.path.isabs(file_path):
                    file_path = os.path.join(os.getcwd(), file_path)
                
                # Check if file exists
                if Path(file_path).exists():
                    artifacts.append({
                        'type': file_type,
                        'path': file_path,
                        'name': Path(file_path).name
                    })
                    logger.debug(f"Code output pattern found: {Path(file_path).name}")
        
        return artifacts
    
    def _extract_artifacts(self, result: Any) -> List[Dict[str, str]]:
        """Extract generated artifacts from result with enhanced error handling"""
        artifacts = []
        
        try:
            # Parse result for file paths and artifact IDs
            if isinstance(result, dict):
                # Handle structured artifacts from parsing tools
                if 'artifacts' in result and isinstance(result['artifacts'], list):
                    for artifact_info in result['artifacts']:
                        try:
                            if isinstance(artifact_info, dict) and 'path' in artifact_info:
                                path = artifact_info['path']
                                if Path(path).exists():
                                    artifacts.append({
                                        'type': artifact_info.get('type', 'file'),
                                        'path': path,
                                        'name': artifact_info.get('name', Path(path).name)
                                    })
                                    logger.info(f"Extracted artifact: {artifact_info.get('name', 'Unknown')} at {path}")
                                else:
                                    logger.warning(f"Artifact path does not exist: {path}")
                        except Exception as e:
                            logger.warning(f"Error processing artifact info: {e}")
                            continue
                
                # Handle generated_files list from parsing tools
                if 'generated_files' in result and isinstance(result['generated_files'], list):
                    for file_path in result['generated_files']:
                        try:
                            if isinstance(file_path, str) and Path(file_path).exists():
                                artifacts.append({
                                    'type': 'preview_file',
                                    'path': file_path,
                                    'name': Path(file_path).name
                                })
                                logger.info(f"Extracted generated file: {Path(file_path).name}")
                        except Exception as e:
                            logger.warning(f"Error processing generated file: {e}")
                            continue
                
                # Look for common artifact patterns (existing logic with error handling)
                path_fields = [
                    ('output_path', 'file', 'Generated File'),
                    ('chart_path', 'chart', 'Generated Chart'),
                    ('artifact_path', 'artifact', 'Generated Artifact')
                ]
                
                for field, file_type, default_name in path_fields:
                    if field in result:
                        try:
                            path = result[field]
                            if path and Path(path).exists():
                                artifacts.append({
                                    'type': file_type,
                                    'path': path,
                                    'name': result.get('name', default_name)
                                })
                        except Exception as e:
                            logger.warning(f"Error processing {field}: {e}")
                            continue
                
                # Handle save_artifact_tool output
                if 'path' in result and result.get('status') == 'success':
                    try:
                        path = result['path']
                        if Path(path).exists():
                            artifacts.append({
                                'type': 'artifact',
                                'path': path,
                                'name': Path(path).name
                            })
                    except Exception as e:
                        logger.warning(f"Error processing artifact path: {e}")
                        
            elif isinstance(result, str):
                # Enhanced string parsing for various tool outputs
                patterns = [
                    # Chart generator
                    (r'Chart generated successfully: (.+)', 'chart', 'Generated Chart'),
                    # Excel generator
                    (r'Excel file created successfully: (.+)', 'file', 'Generated Excel File'),
                    (r'Excel file saved to: (.+)', 'file', 'Generated Excel File'),
                    # Word generator
                    (r'Word document created successfully: (.+)', 'file', 'Generated Word Document'),
                    (r'Document saved to: (.+)', 'file', 'Generated Document'),
                    # Save artifact tool
                    (r'Artifact saved successfully: (.+)', 'artifact', 'Generated Artifact'),
                    # Parsing tool patterns
                    (r'Excel parsed successfully\. Generated (\d+) preview file\(s\)\.', 'message', 'Excel Preview'),
                    (r'Word document parsed successfully\. Generated (\d+) preview file\(s\)\.', 'message', 'Word Preview'),
                    # Generic file paths (temp/ directory)
                    (r'(temp[/\\][\w\\/.-]+\.\w+)', 'file', 'Generated File'),
                    (r'(temp[/\\]previews[/\\][\w\\/.-]+\.\w+)', 'preview_file', 'Preview File'),
                ]
                
                import re
                for pattern, file_type, default_name in patterns:
                    try:
                        matches = re.findall(pattern, result, re.IGNORECASE)
                        for match in matches:
                            path = match.strip().strip('"\'')
                            if path and Path(path).exists():
                                artifacts.append({
                                    'type': file_type,
                                    'path': path,
                                    'name': Path(path).name if Path(path).name else default_name
                                })
                    except Exception as e:
                        logger.warning(f"Error processing pattern {pattern}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error in _extract_artifacts: {e}", exc_info=True)
        
        return artifacts

    def _create_artifact_records(self, artifacts: List[Dict[str, str]], message) -> None:
        """Create Artifact database records for generated files"""
        from apps.chat.models import Artifact
        
        successful_artifacts = 0
        failed_artifacts = 0
        
        for artifact_data in artifacts:
            try:
                file_path = Path(artifact_data['path'])
                
                # Enhanced validation and logging
                if not file_path.exists():
                    logger.warning(f"Artifact registration failed - file not found: {file_path} (type: {artifact_data.get('type', 'unknown')})")
                    failed_artifacts += 1
                    continue
                
                # Get file metadata with error handling
                try:
                    file_size = file_path.stat().st_size
                    if file_size == 0:
                        logger.warning(f"Artifact registration skipped - empty file: {file_path}")
                        failed_artifacts += 1
                        continue
                except OSError as stat_error:
                    logger.error(f"Artifact registration failed - cannot stat file {file_path}: {stat_error}")
                    failed_artifacts += 1
                    continue
                
                mime_type = self._get_mime_type(file_path)
                
                # Create Artifact record with enhanced error handling
                artifact = Artifact.objects.create(
                    message=message,
                    file_path=str(file_path),
                    file_name=file_path.name,
                    file_type=mime_type,
                    file_size=file_size,
                    expires_at=timezone.now() + timedelta(hours=24)  # 24-hour expiration
                )
                
                successful_artifacts += 1
                logger.info(f"[OK] Artifact registered successfully: {artifact.file_name} ({artifact.file_size} bytes, type: {artifact_data.get('type', 'unknown')})")
                
            except Exception as e:
                failed_artifacts += 1
                logger.error(f"[FAIL] Artifact registration failed for {artifact_data.get('path', 'unknown path')}: {str(e)}", exc_info=True)
        
        # Summary logging
        total_artifacts = successful_artifacts + failed_artifacts
        if total_artifacts > 0:
            logger.info(f"Artifact registration summary: {successful_artifacts}/{total_artifacts} successful, {failed_artifacts} failed")
        
        # Update message metadata with artifact counts
        if hasattr(message, 'artifacts') and isinstance(message.artifacts, list):
            # Add artifact count metadata to the message
            artifact_summary = {
                'total_generated': total_artifacts,
                'successfully_registered': successful_artifacts,
                'failed_registration': failed_artifacts
            }
            if not any(item.get('summary') for item in message.artifacts if isinstance(item, dict)):
                message.artifacts.append({'summary': artifact_summary})
                message.save()

    def _get_mime_type(self, file_path: Path) -> str:
        """Determine MIME type for file"""
        # Try to guess from file extension first
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            return mime_type
        
        # Fallback to extension-based mapping
        ext = file_path.suffix.lower()
        type_mapping = {
            '.pdf': 'application/pdf',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.zip': 'application/zip',
            '.md': 'text/markdown'
        }
        
        return type_mapping.get(ext, 'application/octet-stream')

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [tool.name for tool in self.tools]