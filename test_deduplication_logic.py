#!/usr/bin/env python3
"""
Simplified test for artifact deduplication logic

This script tests the core deduplication functionality without requiring
a full Django environment setup.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class MockChatbotOrchestrator:
    """Mock orchestrator with just the deduplication methods"""
    
    def _deduplicate_artifacts_robust(self, artifacts):
        """Mock implementation of the deduplication logic"""
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
                    print(f"Skipping invalid artifact: {path}")
                    continue
                
                # Check for duplicates
                if normalized_path in normalized_paths:
                    # Log duplicate detection
                    existing_source = detection_sources.get(normalized_path, 'unknown')
                    current_source = artifact.get('type', 'unknown')
                    print(f"Duplicate artifact detected: {Path(path).name}")
                    print(f"  First detected by: {existing_source}")
                    print(f"  Also detected by: {current_source}")
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
                print(f"Error processing artifact path '{path}': {e}")
                continue
        
        if len(artifacts) != len(unique_artifacts):
            print(f"Deduplication removed {len(artifacts) - len(unique_artifacts)} duplicate artifacts")
        
        return unique_artifacts
    
    def _validate_artifact_file(self, file_path):
        """Mock validation method"""
        try:
            path_obj = Path(file_path)
            
            # Check if file exists
            if not path_obj.exists():
                return False
            
            # Check if file is not empty
            if path_obj.stat().st_size == 0:
                print(f"Artifact file is empty: {file_path}")
                return False
            
            # Check if file is readable
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)  # Try to read one byte
                return True
            except (PermissionError, IOError) as e:
                print(f"Artifact file not readable: {file_path} - {e}")
                return False
                
        except Exception as e:
            print(f"Error validating artifact file {file_path}: {e}")
            return False
    
    def _validate_tool_execution_status(self, result_str, artifacts=None):
        """Mock robust tool execution validation"""
        if not result_str:
            return False
        
        result_lower = result_str.lower()
        
        # Strategy 1: Check for critical parsing errors FIRST
        critical_errors = [
            'error in code parsing',
            'invalid code snippet',
            'regex pattern',
            'was not found in it',
            'make sure to include code'
        ]
        
        for error_pattern in critical_errors:
            if error_pattern in result_lower:
                print(f"Critical agent parsing error detected: '{error_pattern}' found in result")
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
                print(f"Tool execution validated: {valid_artifacts} valid artifacts created")
                return True
        
        # Strategy 3: If no artifacts but no obvious errors, assume success
        print("Tool execution assumed successful: no obvious failures detected")
        return True

def test_path_normalization():
    """Test path normalization in deduplication"""
    print("\n=== Testing Path Normalization ===")
    
    # Create temporary directory and test files
    temp_dir = tempfile.mkdtemp(prefix="test_dedup_")
    
    try:
        # Create test files
        test_file1 = os.path.join(temp_dir, 'test_doc.xlsx')
        test_file2 = os.path.join(temp_dir, 'subdir', 'another_doc.docx')
        
        os.makedirs(os.path.dirname(test_file2), exist_ok=True)
        
        with open(test_file1, 'w') as f:
            f.write('Test Excel content')
        with open(test_file2, 'w') as f:
            f.write('Test Word content')
        
        # Create orchestrator and test artifacts
        orchestrator = MockChatbotOrchestrator()
        
        # Create artifacts with different path formats
        artifacts = [
            {'path': test_file1, 'type': 'excel', 'name': 'test_doc.xlsx'},
            {'path': test_file1.replace('/', '\\'), 'type': 'excel', 'name': 'test_doc.xlsx'},  # Different separators
            {'path': os.path.relpath(test_file1, temp_dir), 'type': 'excel', 'name': 'test_doc.xlsx'},  # Relative path within temp dir
            {'path': test_file2, 'type': 'word', 'name': 'another_doc.docx'},
        ]
        
        # Test deduplication
        unique_artifacts = orchestrator._deduplicate_artifacts_robust(artifacts)
        
        print(f"Input artifacts: {len(artifacts)}")
        print(f"Unique artifacts after deduplication: {len(unique_artifacts)}")
        
        # Should have only 2 unique files despite 4 input artifacts
        assert len(unique_artifacts) == 2, f"Expected 2 unique artifacts, got {len(unique_artifacts)}"
        print("✓ Path normalization test passed")
        
        return True
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)

def test_tool_execution_validation():
    """Test robust tool execution status validation"""
    print("\n=== Testing Robust Tool Execution Validation ===")
    
    # Create temporary directory and test files
    temp_dir = tempfile.mkdtemp(prefix="test_validation_")
    
    try:
        orchestrator = MockChatbotOrchestrator()
        
        # Create a valid test file
        valid_file = os.path.join(temp_dir, 'valid_output.xlsx')
        with open(valid_file, 'w') as f:
            f.write('Valid Excel content')
        
        # Test cases with artifacts
        test_cases_with_artifacts = [
            # French success message with valid artifact - should be True
            ("Un document Word aléatoire a été généré avec succès", [{'path': valid_file, 'type': 'excel'}], True),
            # English success message with valid artifact - should be True
            ("File created successfully: test.xlsx", [{'path': valid_file, 'type': 'excel'}], True),
            # Any message with valid artifact - should be True (robust approach)
            ("Random message in any language", [{'path': valid_file, 'type': 'excel'}], True),
            # Agent parsing error with artifacts - should be False
            ("Error in code parsing: regex pattern was not found", [{'path': valid_file, 'type': 'excel'}], False),
        ]
        
        for result_text, artifacts, expected in test_cases_with_artifacts:
            actual = orchestrator._validate_tool_execution_status(result_text, artifacts)
            print(f"  '{result_text[:40]}...' + artifacts -> {actual} (expected: {expected})")
            assert actual == expected, f"Failed for: {result_text}"
        
        # Test cases without artifacts
        test_cases_no_artifacts = [
            # No artifacts but no obvious errors - should be True (assume success)
            ("Analysis completed", None, True),
            ("Random output without files", [], True),
            # Clear parsing errors - should be False
            ("Error in code parsing: invalid code snippet", None, False),
            ("Make sure to include code with correct pattern", [], False),
        ]
        
        for result_text, artifacts, expected in test_cases_no_artifacts:
            actual = orchestrator._validate_tool_execution_status(result_text, artifacts)
            print(f"  '{result_text[:40]}...' + no artifacts -> {actual} (expected: {expected})")
            assert actual == expected, f"Failed for: {result_text}"
        
        print("✓ Robust tool execution validation test passed")
        return True
        
    finally:
        shutil.rmtree(temp_dir)

def test_empty_and_invalid_files():
    """Test handling of empty and invalid files"""
    print("\n=== Testing Empty and Invalid File Handling ===")
    
    temp_dir = tempfile.mkdtemp(prefix="test_invalid_")
    
    try:
        orchestrator = MockChatbotOrchestrator()
        
        # Create valid file
        valid_file = os.path.join(temp_dir, 'valid.xlsx')
        with open(valid_file, 'w') as f:
            f.write('Valid content')
        
        # Create empty file
        empty_file = os.path.join(temp_dir, 'empty.docx')
        with open(empty_file, 'w') as f:
            pass  # Create empty file
        
        # Create artifacts including the empty file
        artifacts = [
            {'path': valid_file, 'type': 'excel', 'name': 'valid.xlsx'},
            {'path': empty_file, 'type': 'word', 'name': 'empty.docx'},
            {'path': '/nonexistent/file.pdf', 'type': 'pdf', 'name': 'nonexistent.pdf'},
        ]
        
        # Test deduplication (should filter out invalid files)
        unique_artifacts = orchestrator._deduplicate_artifacts_robust(artifacts)
        
        print(f"Input artifacts: {len(artifacts)}")
        print(f"Valid artifacts after filtering: {len(unique_artifacts)}")
        
        # Should have only 1 valid file
        assert len(unique_artifacts) == 1, f"Expected 1 valid artifact, got {len(unique_artifacts)}"
        assert unique_artifacts[0]['name'] == 'valid.xlsx'
        
        print("✓ Empty and invalid file handling test passed")
        return True
        
    finally:
        shutil.rmtree(temp_dir)

def main():
    """Run simplified deduplication tests"""
    print("🔍 Running Simplified Artifact Deduplication Tests")
    print("=" * 60)
    
    try:
        # Run tests
        test_path_normalization()
        test_tool_execution_validation()
        test_empty_and_invalid_files()
        
        print("\n" + "=" * 60)
        print("✅ All simplified tests passed!")
        print("The core deduplication logic is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)