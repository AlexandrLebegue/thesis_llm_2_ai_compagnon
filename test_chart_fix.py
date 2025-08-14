#!/usr/bin/env python3
"""
Test script to verify the chart generation tool fix.
Tests that the tool now accepts both string and object inputs.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

from apps.agents.tools.generate_chart_tool import GenerateChartTool

def test_chart_string_input():
    """Test chart generation with JSON string input"""
    print("🧪 Testing chart generation with JSON string input...")
    
    tool = GenerateChartTool()
    
    # Test with JSON string
    json_input = '{"type": "bar", "title": "Test Chart", "data": {"x": ["A", "B", "C"], "y": [1, 2, 3]}}'
    
    result = tool.forward(json_input)
    
    success = result.get('status') == 'success' and 'chart_path' in result
    print(f"📊 String input result: {'✅ PASS' if success else '❌ FAIL'}")
    if success:
        print(f"   Generated chart: {result['chart_path']}")
    else:
        print(f"   Error: {result.get('error', 'Unknown error')}")
    
    return success

def test_chart_object_input():
    """Test chart generation with dict object input"""
    print("\n🧪 Testing chart generation with dict object input...")
    
    tool = GenerateChartTool()
    
    # Test with Python dict
    dict_input = {
        "type": "bar", 
        "title": "Test Chart Object", 
        "data": {
            "x": ["Janvier", "Fevrier", "Mars"], 
            "y": [100, 150, 200]
        }
    }
    
    result = tool.forward(dict_input)
    
    success = result.get('status') == 'success' and 'chart_path' in result
    print(f"📊 Object input result: {'✅ PASS' if success else '❌ FAIL'}")
    if success:
        print(f"   Generated chart: {result['chart_path']}")
    else:
        print(f"   Error: {result.get('error', 'Unknown error')}")
    
    return success

def test_chart_invalid_input():
    """Test chart generation with invalid input types"""
    print("\n🧪 Testing chart generation with invalid input...")
    
    tool = GenerateChartTool()
    
    # Test with integer (should fall back gracefully)
    invalid_input = 12345
    
    result = tool.forward(invalid_input)
    
    # Should either succeed with fallback or fail gracefully
    success = 'status' in result  # Should at least return a status
    print(f"📊 Invalid input handling: {'✅ PASS' if success else '❌ FAIL'}")
    print(f"   Status: {result.get('status', 'No status')}")
    if result.get('status') == 'error':
        print(f"   Error (expected): {result.get('error', 'Unknown error')}")
    
    return success

def main():
    """Run all tests"""
    print("🚀 Testing chart generation tool input handling...\n")
    
    tests = [
        ("String Input", test_chart_string_input),
        ("Object Input", test_chart_object_input),
        ("Invalid Input", test_chart_invalid_input)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            results.append((test_name, False))
            print(f"❌ {test_name}: FAIL - {e}")
    
    # Summary
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Chart tool now handles both string and object inputs.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)