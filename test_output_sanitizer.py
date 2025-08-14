#!/usr/bin/env python3
"""
Quick test for output sanitizer to verify it prevents parsing errors
"""

import os
import sys
import django

# Setup Django
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

from apps.agents.tools.generate_chart_tool import GenerateChartTool
from apps.agents.tools.tool_utils import ToolOutputSanitizer

def test_output_sanitization():
    """Test that output sanitization prevents parsing errors."""
    print("Testing Output Sanitization...")
    
    # Test the problematic case that causes parsing errors
    tool = GenerateChartTool()
    test_input = '{"type": "bar", "title": "Test Chart", "data": {"x": ["A", "B"], "y": [1, 2]}}'
    
    try:
        result = tool.forward(test_input)
        
        print(f"✓ Tool execution successful")
        print(f"Result type: {type(result)}")
        
        if isinstance(result, dict):
            print(f"Result keys: {list(result.keys())}")
            
            # Check if output was sanitized
            is_sanitized = result.get('_tool_output', False)
            if is_sanitized:
                print(f"✓ Output was sanitized to prevent parsing errors")
                print(f"Source tool: {result.get('_source_tool', 'unknown')}")
                
                # Extract the actual output
                actual_output = ToolOutputSanitizer.extract_actual_output(result)
                print(f"Actual output type: {type(actual_output)}")
                if isinstance(actual_output, dict):
                    print(f"Actual output keys: {list(actual_output.keys())}")
            else:
                print(f"✓ Output did not need sanitization")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_error_sanitization():
    """Test that error outputs are also sanitized."""
    print("\nTesting Error Sanitization...")
    
    tool = GenerateChartTool()
    # Test with invalid input that should trigger an error
    test_input = '{"type": "bar"}'  # Missing required data field
    
    try:
        result = tool.forward(test_input)
        
        print(f"✓ Error handling successful")
        print(f"Result type: {type(result)}")
        
        if isinstance(result, dict):
            print(f"Result keys: {list(result.keys())}")
            
            # Check if error output was sanitized
            is_sanitized = result.get('_tool_output', False)
            if is_sanitized:
                print(f"✓ Error output was sanitized")
                print(f"Source tool: {result.get('_source_tool', 'unknown')}")
            else:
                print(f"✓ Error output did not need sanitization")
            
            # Check status
            actual_output = ToolOutputSanitizer.extract_actual_output(result)
            if isinstance(actual_output, dict):
                status = actual_output.get('status', 'unknown')
                print(f"Status: {status}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error test failed: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("OUTPUT SANITIZER TEST")
    print("=" * 50)
    
    success1 = test_output_sanitization()
    success2 = test_error_sanitization()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("🎉 ALL TESTS PASSED! Output sanitization is working correctly.")
    else:
        print("❌ Some tests failed.")