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
from django.conf import settings

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
                "datetime", "pathlib", "io", "base64", "requests", "string"
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
        message=None,
        conversation_id: str = None
    ) -> Dict[str, Any]:
        """Process user request with context and conversation history"""
        
        try:
            # Build prompt with context and conversation history
            prompt = self._build_prompt(instruction, context, conversation_id)
            
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
                    # Cleanup any orphaned files from failed execution
                    self._cleanup_orphaned_artifacts(files_before, self._get_temp_files_snapshot(temp_dir))
                    return {
                        'status': 'error',
                        'error': 'Agent returned no response'
                    }
                
                # Convert result to string if it's not already
                result_str = str(result) if result is not None else "No response generated"
                
                # Track temp directory state after agent execution
                files_after = self._get_temp_files_snapshot(temp_dir)
                
                # Extract artifacts from multiple sources first
                artifacts = self._extract_artifacts_enhanced(result, files_before, files_after)
                
                # Validate tool execution status using the artifacts as evidence
                tool_execution_successful = self._validate_tool_execution_status(result_str, artifacts)
                
                # Only filter artifacts if we detect actual execution failures
                # (not just lack of success keywords)
                if not tool_execution_successful:
                    logger.warning("Tool execution failure detected - filtering artifacts")
                    artifacts = self._filter_artifacts_for_failed_tools(artifacts, result_str)
                
                # Create Artifact database records if message is provided and artifacts are valid
                if message and artifacts:
                    self._create_artifact_records(artifacts, message, result)
                elif not tool_execution_successful:
                    # Cleanup orphaned files from failed tools
                    self._cleanup_orphaned_artifacts(files_before, files_after)
                
                # Process results
                return {
                    'status': 'success',
                    'result': result_str,
                    'artifacts': artifacts,
                    'tool_execution_successful': tool_execution_successful
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
    
    def _build_prompt(self, instruction: str, context: Dict[str, Any], conversation_id: str = None) -> str:
        """Build prompt with document context and conversation history"""
        prompt_parts = []
        
        # Add conversation history
        conversation_history = self._get_conversation_history(conversation_id)
        if conversation_history:
            prompt_parts.append("=== Conversation History ===")
            prompt_parts.extend(conversation_history)
            prompt_parts.append("")  # Empty line separator
        
        # Add document context
        if context.get('documents'):
            prompt_parts.append("=== Available Documents ===")
            for doc in context['documents']:
                prompt_parts.append(f"- {doc['name']} ({doc['type']}): {doc['summary']}")
            prompt_parts.append("")  # Empty line separator
        
        # Add current instruction
        prompt_parts.append("=== Current Request ===")
        prompt_parts.append(f"User request: {instruction}")
        
        return '\n'.join(prompt_parts)
    
    def _get_conversation_history(self, conversation_id: str = None) -> List[str]:
        """Fetch recent conversation history for context"""
        if not conversation_id:
            return []
        
        try:
            from apps.chat.models import Conversation, Message
            
            # Get conversation object
            conversation = Conversation.objects.get(id=conversation_id)
            
            # Get last N messages (excluding the current message being processed)
            max_history = getattr(settings, 'MAX_CONVERSATION_HISTORY', 10)
            messages = Message.objects.filter(
                conversation=conversation
            ).exclude(
                role='system'  # Exclude system messages
            ).order_by('-created_at')[:max_history]
            
            # Format messages in chronological order (oldest first)
            history_lines = []
            for message in reversed(messages):
                role_display = "User" if message.role == "user" else "Assistant"
                # Truncate very long messages for context
                content = message.content
                if len(content) > 500:
                    content = content[:500] + "..."
                
                history_lines.append(f"{role_display}: {content}")
            
            return history_lines
            
        except Exception as e:
            logger.warning(f"Error fetching conversation history: {str(e)}")
            return []
    
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
        
        # Enhanced deduplication with path normalization
        unique_artifacts = self._deduplicate_artifacts_robust(artifacts)
        
        logger.info(f"Enhanced artifact extraction found {len(unique_artifacts)} unique artifacts from {len(artifacts)} total detections")
        for i, artifact in enumerate(unique_artifacts):
            logger.debug(f"  Unique artifact {i+1}: {artifact.get('name', 'unknown')} ({artifact.get('type', 'unknown')})")
        
        return unique_artifacts
    
    def _deduplicate_artifacts_robust(self, artifacts: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Robust deduplication with path normalization and validation
        
        This method handles:
        - Path normalization (backslash vs forward slash)
        - Relative vs absolute path matching
        - Case sensitivity on Windows
        - File existence validation
        - Detection source tracking
        """
        import os
        from pathlib import Path
        
        # Track detection sources for debugging
        detection_sources = {}
        normalized_paths = {}
        unique_artifacts = []
        
        for artifact in artifacts:
            path = artifact.get('path', '')
            if not path:
                continue
                
            # Normalize the path for comparison
            try:
                # Convert to absolute path if relative
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
                
                # Normalize path separators and case
                normalized_path = os.path.normpath(path).lower()
                
                # Validate file exists and is not empty
                if not self._validate_artifact_file(path):
                    logger.debug(f"Skipping invalid artifact: {path}")
                    continue
                
                # Check for duplicates
                if normalized_path in normalized_paths:
                    # Log duplicate detection
                    existing_source = detection_sources.get(normalized_path, 'unknown')
                    current_source = artifact.get('type', 'unknown')
                    logger.debug(f"Duplicate artifact detected: {Path(path).name}")
                    logger.debug(f"  First detected by: {existing_source}")
                    logger.debug(f"  Also detected by: {current_source}")
                    continue
                
                # Add to unique artifacts
                normalized_paths[normalized_path] = path
                detection_sources[normalized_path] = artifact.get('type', 'unknown')
                
                # Enhance artifact with normalized path
                enhanced_artifact = artifact.copy()
                enhanced_artifact['normalized_path'] = normalized_path
                enhanced_artifact['detection_source'] = artifact.get('type', 'unknown')
                
                unique_artifacts.append(enhanced_artifact)
                
            except Exception as e:
                logger.warning(f"Error processing artifact path '{path}': {e}")
                continue
        
        if len(artifacts) != len(unique_artifacts):
            logger.info(f"Deduplication removed {len(artifacts) - len(unique_artifacts)} duplicate artifacts")
        
        return unique_artifacts
    
    def _validate_artifact_file(self, file_path: str) -> bool:
        """
        Validate that an artifact file is valid for registration
        
        Checks:
        - File exists
        - File is not empty
        - File is readable
        - File is in expected temp directory (security)
        """
        try:
            path_obj = Path(file_path)
            
            # Check if file exists
            if not path_obj.exists():
                return False
            
            # Check if file is not empty
            if path_obj.stat().st_size == 0:
                logger.debug(f"Artifact file is empty: {file_path}")
                return False
            
            # Security check: ensure file is in temp directory
            temp_dir = os.path.abspath('temp')
            file_abs_path = os.path.abspath(file_path)
            if not file_abs_path.startswith(temp_dir):
                logger.warning(f"Artifact file outside temp directory: {file_path}")
                return False
            
            # Check if file is readable
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)  # Try to read one byte
                return True
            except (PermissionError, IOError) as e:
                logger.debug(f"Artifact file not readable: {file_path} - {e}")
                return False
                
        except Exception as e:
            logger.debug(f"Error validating artifact file {file_path}: {e}")
            return False
    
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

    def _create_artifact_records(self, artifacts: List[Dict[str, str]], message, agent_result=None) -> None:
        """Create Artifact database records for generated files with duplicate prevention"""
        from apps.chat.models import Artifact
        from django.db import IntegrityError
        
        successful_artifacts = 0
        failed_artifacts = 0
        duplicate_artifacts = 0
        
        for artifact_data in artifacts:
            try:
                file_path = Path(artifact_data['path'])
                
                # Use enhanced validation from deduplication process
                if not self._validate_artifact_file(str(file_path)):
                    logger.warning(f"Artifact registration failed - validation failed: {file_path} (type: {artifact_data.get('detection_source', 'unknown')})")
                    failed_artifacts += 1
                    continue
                
                # Get file metadata with error handling
                try:
                    file_size = file_path.stat().st_size
                except OSError as stat_error:
                    logger.error(f"Artifact registration failed - cannot stat file {file_path}: {stat_error}")
                    failed_artifacts += 1
                    continue
                
                mime_type = self._get_mime_type(file_path)
                
                # Check for existing artifacts with same file path for this message
                normalized_path = artifact_data.get('normalized_path', str(file_path).lower())
                existing_artifacts = Artifact.objects.filter(
                    message=message,
                    file_path__iexact=str(file_path)
                ).exists()
                
                if existing_artifacts:
                    duplicate_artifacts += 1
                    logger.debug(f"Artifact already exists for message: {file_path.name}")
                    continue
                
                # Extract preview HTML for Word and Excel documents
                preview_html = None
                if (mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or
                    file_path.suffix.lower() == '.docx' or
                    mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or
                    mime_type == 'application/vnd.ms-excel' or
                    file_path.suffix.lower() in ['.xlsx', '.xls']):
                    preview_html = self._extract_preview_html(file_path, agent_result)
                
                # Create Artifact record with enhanced error handling
                try:
                    artifact = Artifact.objects.create(
                        message=message,
                        file_path=str(file_path),
                        file_name=file_path.name,
                        file_type=mime_type,
                        file_size=file_size,
                        preview_html=preview_html,
                        expires_at=timezone.now() + timedelta(hours=24)  # 24-hour expiration
                    )
                    
                    successful_artifacts += 1
                    detection_source = artifact_data.get('detection_source', 'unknown')
                    logger.info(f"[OK] Artifact registered: {artifact.file_name} ({artifact.file_size} bytes, detected by: {detection_source})")
                    
                except IntegrityError as integrity_error:
                    # Handle rare race condition where duplicate is created between check and insert
                    duplicate_artifacts += 1
                    logger.debug(f"Artifact registration prevented duplicate: {file_path.name} - {integrity_error}")
                
            except Exception as e:
                failed_artifacts += 1
                logger.error(f"[FAIL] Artifact registration failed for {artifact_data.get('path', 'unknown path')}: {str(e)}", exc_info=True)
        
        # Enhanced summary logging
        total_attempts = successful_artifacts + failed_artifacts + duplicate_artifacts
        if total_attempts > 0:
            logger.info(f"Artifact registration summary: {successful_artifacts} registered, {duplicate_artifacts} duplicates prevented, {failed_artifacts} failed ({total_attempts} total)")
        
        # Log detection method effectiveness
        detection_methods = {}
        for artifact_data in artifacts:
            method = artifact_data.get('detection_source', 'unknown')
            detection_methods[method] = detection_methods.get(method, 0) + 1
        
        if detection_methods:
            logger.debug(f"Detection method breakdown: {detection_methods}")
        
        # Update message metadata with artifact counts
        if hasattr(message, 'artifacts') and isinstance(message.artifacts, list):
            # Add artifact count metadata to the message
            artifact_summary = {
                'total_generated': total_attempts,
                'successfully_registered': successful_artifacts,
                'failed_registration': failed_artifacts,
                'duplicates_prevented': duplicate_artifacts
            }
            if not any(item.get('summary') for item in message.artifacts if isinstance(item, dict)):
                message.artifacts.append({'summary': artifact_summary})
                message.save()

    def _validate_tool_execution_status(self, result_str: str, artifacts: list = None) -> bool:
        """
        Robust tool execution validation based on actual file creation and tool outputs
        
        This method validates tool success by checking:
        1. First, check for critical parsing errors (highest priority)
        2. Then validate if detected artifacts are actually valid files
        3. Finally, assume success if no obvious problems detected
        
        Args:
            result_str: Agent result (used minimally)
            artifacts: List of detected artifacts to validate
            
        Returns:
            bool: True if tools executed successfully
        """
        if not result_str:
            return False
        
        result_lower = result_str.lower()
        
        # Strategy 1: Check for critical parsing errors FIRST
        # These indicate the agent itself failed and override everything else
        critical_errors = [
            'error in code parsing',
            'invalid code snippet',
            'regex pattern',
            'was not found in it',
            'make sure to include code'
        ]
        
        for error_pattern in critical_errors:
            if error_pattern in result_lower:
                logger.debug(f"Critical agent parsing error detected: '{error_pattern}' found in result")
                return False
        
        # Strategy 2: If we have valid artifacts, tools likely succeeded
        if artifacts:
            valid_artifacts = 0
            for artifact in artifacts:
                file_path = artifact.get('path', '')
                if file_path and self._validate_artifact_file(file_path):
                    valid_artifacts += 1
            
            # If we have valid files and no critical errors, execution was successful
            if valid_artifacts > 0:
                logger.debug(f"Tool execution validated: {valid_artifacts} valid artifacts created")
                return True
        
        # Strategy 3: If no artifacts but no obvious errors, assume success
        # This handles cases where tools don't create files (e.g., analysis tools)
        logger.debug("Tool execution assumed successful: no obvious failures detected")
        return True

    def _filter_artifacts_for_failed_tools(self, artifacts: List[Dict[str, str]], result_str: str) -> List[Dict[str, str]]:
        """
        Filter artifacts when tools have failed execution
        
        This method helps prevent registration of invalid artifacts from failed tool executions
        while still allowing valid artifacts that were created successfully.
        """
        if not artifacts:
            return artifacts
        
        filtered_artifacts = []
        result_lower = result_str.lower()
        
        for artifact in artifacts:
            file_path = artifact.get('path', '')
            file_name = Path(file_path).name if file_path else ''
            
            # Always validate the file regardless of failure status
            if not self._validate_artifact_file(file_path):
                logger.debug(f"Filtered out invalid artifact from failed tool: {file_name}")
                continue
            
            # Check if this specific file is mentioned positively in the result
            if file_name.lower() in result_lower:
                # Look for positive context around this file mention
                context_start = max(0, result_lower.find(file_name.lower()) - 50)
                context_end = min(len(result_lower), result_lower.find(file_name.lower()) + len(file_name) + 50)
                context = result_lower[context_start:context_end]
                
                if any(indicator in context for indicator in ['successfully', 'created', 'generated', 'saved']):
                    filtered_artifacts.append(artifact)
                    logger.debug(f"Kept artifact with positive context: {file_name}")
                else:
                    logger.debug(f"Filtered out artifact without positive context: {file_name}")
            else:
                # File not mentioned in result - likely from filesystem detection of orphaned file
                logger.debug(f"Filtered out unmentioned artifact from failed tool: {file_name}")
        
        logger.info(f"Filtered artifacts for failed tools: {len(filtered_artifacts)} kept out of {len(artifacts)} total")
        return filtered_artifacts

    def _cleanup_orphaned_artifacts(self, files_before: Dict[str, float], files_after: Dict[str, float]) -> None:
        """
        Clean up orphaned files from failed tool executions
        
        This method removes temporary files that were created during failed tool executions
        to prevent them from being detected as artifacts in future runs.
        """
        try:
            import time
            
            # Find new files created during execution
            new_files = set(files_after.keys()) - set(files_before.keys())
            
            cleaned_count = 0
            for file_path in new_files:
                try:
                    path_obj = Path(file_path)
                    if path_obj.exists():
                        # Additional safety check - only clean files in temp directory
                        temp_dir = os.path.abspath('temp')
                        file_abs_path = os.path.abspath(file_path)
                        
                        if file_abs_path.startswith(temp_dir):
                            # Check if file is very recent (created within last few minutes)
                            file_age = time.time() - path_obj.stat().st_mtime
                            if file_age < 300:  # Less than 5 minutes old
                                path_obj.unlink()
                                cleaned_count += 1
                                logger.debug(f"Cleaned up orphaned file: {path_obj.name}")
                            else:
                                logger.debug(f"Skipped cleanup of older file: {path_obj.name}")
                        else:
                            logger.warning(f"Skipped cleanup of file outside temp directory: {file_path}")
                except Exception as cleanup_error:
                    logger.debug(f"Error cleaning up file {file_path}: {cleanup_error}")
                    continue
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} orphaned files from failed tool execution")
                
        except Exception as e:
            logger.warning(f"Error during orphaned artifact cleanup: {e}")

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
    
    def _extract_preview_html(self, file_path: Path, agent_result=None) -> str:
        """Extract preview HTML for Word and Excel documents from tool results or generate it"""
        try:
            # First, try to extract from agent result if it contains preview_html
            if agent_result and isinstance(agent_result, str):
                import ast
                import re
                
                # Look for dictionary representations in the result string
                dict_pattern = r'\{[^{}]*preview_html[^{}]*\}'
                matches = re.findall(dict_pattern, agent_result, re.DOTALL)
                
                for match in matches:
                    try:
                        # Try to safely evaluate the dictionary string
                        result_dict = ast.literal_eval(match)
                        if isinstance(result_dict, dict) and result_dict.get('preview_html'):
                            return result_dict['preview_html']
                    except (ValueError, SyntaxError):
                        continue
            
            # Determine file type and generate preview accordingly
            file_ext = file_path.suffix.lower()
            
            if file_ext == '.docx':
                # Generate Word preview
                try:
                    from apps.agents.tools.word_preview import WordPreviewGenerator
                    preview_result = WordPreviewGenerator.generate_preview(str(file_path))
                    if preview_result['success']:
                        logger.info(f"Generated Word preview HTML for {file_path.name}")
                        return preview_result['preview_html']
                    else:
                        logger.warning(f"Failed to generate Word preview for {file_path.name}: {preview_result.get('error', 'Unknown error')}")
                except ImportError:
                    logger.warning("WordPreviewGenerator not available")
                except Exception as e:
                    logger.error(f"Error generating Word preview for {file_path.name}: {str(e)}")
            
            elif file_ext in ['.xlsx', '.xls']:
                # Generate Excel preview
                try:
                    from apps.agents.tools.excel_preview import ExcelPreviewGenerator
                    preview_result = ExcelPreviewGenerator.generate_preview(str(file_path))
                    if preview_result['success']:
                        logger.info(f"Generated Excel preview HTML for {file_path.name}")
                        return preview_result['preview_html']
                    else:
                        logger.warning(f"Failed to generate Excel preview for {file_path.name}: {preview_result.get('error', 'Unknown error')}")
                except ImportError:
                    logger.warning("ExcelPreviewGenerator not available")
                except Exception as e:
                    logger.error(f"Error generating Excel preview for {file_path.name}: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error extracting preview HTML for {file_path.name}: {str(e)}")
        
        return None

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [tool.name for tool in self.tools]