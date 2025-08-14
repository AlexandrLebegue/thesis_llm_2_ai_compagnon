#!/usr/bin/env python3
"""
Test script for the SmolAgents tool registry system
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

# Now import the tools
from apps.agents.registry import tool_registry
from apps.agents.tools import *  # This will register all tools

def test_tool_registration():
    """Test that tools are properly registered"""
    print("=== Testing Tool Registration ===")
    
    # List all registered tools
    tools = tool_registry.list_tools()
    print(f"Registered tools: {tools}")
    
    expected_tools = ['parse_pdf', 'parse_excel', 'parse_word', 'modify_excel', 'modify_word', 'generate_chart', 'save_artifact']
    
    for tool in expected_tools:
        if tool in tools:
            print(f"✓ {tool} is registered")
        else:
            print(f"✗ {tool} is NOT registered")
    
    print(f"\nTotal tools registered: {len(tools)}")
    return len(tools) >= len(expected_tools)

def test_tool_inspection():
    """Test tool inspection and parameter validation"""
    print("\n=== Testing Tool Inspection ===")
    
    for tool_name in tool_registry.list_tools():
        tool_def = tool_registry.get_tool(tool_name)
        print(f"\nTool: {tool_name}")
        print(f"  Description: {tool_def.description}")
        print(f"  Parameters: {list(tool_def.parameters.keys())}")
        
        # Check parameter details
        for param_name, param_info in tool_def.parameters.items():
            required = "required" if param_info['required'] else "optional"
            param_type = param_info['type'].__name__ if hasattr(param_info['type'], '__name__') else str(param_info['type'])
            print(f"    - {param_name}: {param_type} ({required})")

def test_save_artifact_tool():
    """Test the save_artifact tool with simple content"""
    print("\n=== Testing save_artifact Tool ===")
    
    try:
        # Test with string content
        result = tool_registry.execute_tool(
            'save_artifact',
            content="Hello, World! This is a test artifact.",
            file_type="txt"
        )
        
        if result.get('status') == 'success':
            print("✓ save_artifact tool executed successfully")
            print(f"  Artifact ID: {result['artifact_id']}")
            print(f"  Path: {result['path']}")
            
            # Check if file was created
            if Path(result['path']).exists():
                print("✓ Artifact file was created")
                return True
            else:
                print("✗ Artifact file was NOT created")
                return False
        else:
            print(f"✗ save_artifact tool failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ Exception in save_artifact test: {str(e)}")
        return False

def test_generate_chart_tool():
    """Test the generate_chart tool with sample data"""
    print("\n=== Testing generate_chart Tool ===")
    
    try:
        # Test with sample data
        sample_data = {
            'data': {
                'x': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
                'y': [10, 15, 13, 17, 20]
            },
            'type': 'bar',
            'title': 'Test Chart',
            'xlabel': 'Months',
            'ylabel': 'Values'
        }
        
        result = tool_registry.execute_tool('generate_chart', data_spec=sample_data)
        
        if result.get('status') == 'success':
            print("✓ generate_chart tool executed successfully")
            print(f"  Chart path: {result['chart_path']}")
            
            # Check if chart file was created
            if Path(result['chart_path']).exists():
                print("✓ Chart file was created")
                return True
            else:
                print("✗ Chart file was NOT created")
                return False
        else:
            print(f"✗ generate_chart tool failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"✗ Exception in generate_chart test: {str(e)}")
        return False

def test_parameter_validation():
    """Test parameter validation"""
    print("\n=== Testing Parameter Validation ===")
    
    try:
        # Test missing required parameter
        try:
            tool_registry.execute_tool('save_artifact', content="test")  # Missing file_type
            print("✗ Should have failed due to missing required parameter")
            return False
        except ValueError as e:
            if "missing" in str(e).lower():
                print("✓ Correctly caught missing required parameter")
            else:
                print(f"✗ Unexpected error: {e}")
                return False
        
        # Test non-existent tool
        try:
            tool_registry.execute_tool('non_existent_tool')
            print("✗ Should have failed due to non-existent tool")
            return False
        except ValueError as e:
            if "not found" in str(e).lower():
                print("✓ Correctly caught non-existent tool")
            else:
                print(f"✗ Unexpected error: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Exception in parameter validation test: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("SmolAgents Tool Registry Test Suite")
    print("=" * 50)
    
    tests = [
        test_tool_registration,
        test_tool_inspection,
        test_save_artifact_tool,
        test_generate_chart_tool,
        test_parameter_validation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return True
    else:
        print("❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)