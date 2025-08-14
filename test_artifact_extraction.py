#!/usr/bin/env python3
"""
Test script to verify artifact extraction functionality with CodeAgent
"""

import os
import sys
import logging
import tempfile
import shutil
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
import django
django.setup()

from apps.agents.orchestrator import ChatbotOrchestrator

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_test_files():
    """Create some test files to simulate tool outputs"""
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    test_files = [
        'temp/test_excel.xlsx',
        'temp/test_document.docx',
        'temp/test_chart.png'
    ]
    
    for file_path in test_files:
        Path(file_path).touch()
        logger.info(f"Created test file: {file_path}")
    
    return test_files

def test_filesystem_detection():
    """Test filesystem-based artifact detection"""
    logger.info("=== Testing Filesystem Detection ===")
    
    try:
        # Initialize orchestrator (with dummy session)
        orchestrator = ChatbotOrchestrator(session_id="test_session")
        
        # Get initial snapshot
        temp_dir = os.path.join(os.getcwd(), 'temp')
        files_before = orchestrator._get_temp_files_snapshot(temp_dir)
        logger.info(f"Files before: {len(files_before)}")
        
        # Create some test files
        test_files = create_test_files()
        
        # Get snapshot after
        files_after = orchestrator._get_temp_files_snapshot(temp_dir)
        logger.info(f"Files after: {len(files_after)}")
        
        # Test filesystem artifact extraction
        artifacts = orchestrator._extract_artifacts_from_filesystem(files_before, files_after)
        logger.info(f"Filesystem artifacts detected: {len(artifacts)}")
        
        for artifact in artifacts:
            logger.info(f"  - {artifact['name']} ({artifact['type']}) at {artifact['path']}")
        
        return len(artifacts) > 0
        
    except Exception as e:
        logger.error(f"Filesystem detection test failed: {e}", exc_info=True)
        return False

def test_code_output_parsing():
    """Test parsing of CodeAgent string output"""
    logger.info("=== Testing Code Output Parsing ===")
    
    try:
        orchestrator = ChatbotOrchestrator(session_id="test_session")
        
        # Test various CodeAgent output patterns
        test_outputs = [
            "excel_generator(filename='test_report.xlsx', data=sales_data)",
            "Excel file created successfully: temp/sales_report.xlsx",
            "simple_word_generator(filename='report.docx', content=summary)",
            "Document saved to: temp/analysis_report.docx", 
            "generate_chart(filename='chart.png', data=chart_data)",
            "Chart generated successfully: temp/performance_chart.png"
        ]
        
        for output in test_outputs:
            logger.info(f"Testing output: {output}")
            artifacts = orchestrator._extract_artifacts_from_code_output(output)
            logger.info(f"  Artifacts found: {len(artifacts)}")
            for artifact in artifacts:
                logger.info(f"    - {artifact['name']} ({artifact['type']})")
        
        return True
        
    except Exception as e:
        logger.error(f"Code output parsing test failed: {e}", exc_info=True)
        return False

def test_enhanced_extraction():
    """Test the enhanced artifact extraction method"""
    logger.info("=== Testing Enhanced Extraction ===")
    
    try:
        orchestrator = ChatbotOrchestrator(session_id="test_session")
        
        # Simulate CodeAgent output
        mock_result = "excel_generator called successfully. File saved to: temp/test_output.xlsx"
        
        # Get filesystem snapshots
        temp_dir = os.path.join(os.getcwd(), 'temp')
        files_before = orchestrator._get_temp_files_snapshot(temp_dir)
        
        # Create a test file to simulate tool execution
        test_file = "temp/test_output.xlsx"
        Path(test_file).touch()
        
        files_after = orchestrator._get_temp_files_snapshot(temp_dir)
        
        # Test enhanced extraction
        artifacts = orchestrator._extract_artifacts_enhanced(mock_result, files_before, files_after)
        logger.info(f"Enhanced extraction found: {len(artifacts)} artifacts")
        
        for artifact in artifacts:
            logger.info(f"  - {artifact['name']} ({artifact['type']}) at {artifact['path']}")
        
        return len(artifacts) > 0
        
    except Exception as e:
        logger.error(f"Enhanced extraction test failed: {e}", exc_info=True)
        return False

def cleanup_test_files():
    """Clean up test files"""
    temp_dir = os.path.join(os.getcwd(), 'temp')
    test_patterns = ['test_*.xlsx', 'test_*.docx', 'test_*.png', '*test_output*']
    
    for pattern in test_patterns:
        import glob
        for file_path in glob.glob(os.path.join(temp_dir, pattern)):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up: {file_path}")
            except OSError:
                pass

def main():
    """Run all tests"""
    logger.info("Starting artifact extraction tests...")
    
    results = []
    
    try:
        # Test 1: Filesystem detection
        results.append(("Filesystem Detection", test_filesystem_detection()))
        
        # Test 2: Code output parsing
        results.append(("Code Output Parsing", test_code_output_parsing()))
        
        # Test 3: Enhanced extraction
        results.append(("Enhanced Extraction", test_enhanced_extraction()))
        
    finally:
        # Clean up
        cleanup_test_files()
    
    # Report results
    logger.info("=== Test Results ===")
    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        logger.info("All tests passed! Artifact extraction should work correctly.")
    else:
        logger.error("Some tests failed. There may be issues with artifact extraction.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)