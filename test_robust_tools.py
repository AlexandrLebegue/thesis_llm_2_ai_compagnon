#!/usr/bin/env python3
"""
Comprehensive test suite for robust SmolAgents tools
Tests edge cases, malformed JSON, special characters, and error scenarios.
"""

import os
import sys
import django
import json
import tempfile
from pathlib import Path

# Setup Django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

# Import tools after Django setup
from apps.agents.tools.excel_generator import ExcelGeneratorTool
from apps.agents.tools.generate_chart_tool import GenerateChartTool
from apps.agents.tools.modify_excel_tool import ModifyExcelTool
from apps.agents.tools.save_artifact_tool import SaveArtifactTool
from apps.agents.tools.word_generator import SimpleWordGeneratorTool

class RobustToolTests:
    """Test suite for robust tool implementations."""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
    
    def run_test(self, test_name: str, test_func):
        """Run a single test and record results."""
        print(f"\n--- Testing {test_name} ---")
        try:
            result = test_func()
            if result:
                print(f"✓ PASSED: {test_name}")
                self.tests_passed += 1
                self.test_results.append((test_name, 'PASSED', ''))
            else:
                print(f"✗ FAILED: {test_name}")
                self.tests_failed += 1
                self.test_results.append((test_name, 'FAILED', 'Test function returned False'))
        except Exception as e:
            print(f"✗ ERROR: {test_name} - {str(e)}")
            self.tests_failed += 1
            self.test_results.append((test_name, 'ERROR', str(e)))
    
    def test_json_quote_handling(self):
        """Test various quote formats in JSON inputs."""
        chart_tool = GenerateChartTool()
        
        # Test 1: Single quotes outside, double inside (common case)
        json_single = '{"type": "bar", "title": "Test Chart", "data": {"x": ["A", "B"], "y": [1, 2]}}'
        result1 = chart_tool.forward(json_single)
        
        # Test 2: Mixed quotes with Python-style format
        json_mixed = "{'type': 'bar', 'title': 'Test Chart', 'data': {'x': ['A', 'B'], 'y': [1, 2]}}"
        result2 = chart_tool.forward(json_mixed)
        
        # Test 3: Escaped quotes
        json_escaped = "{\"type\": \"bar\", \"title\": \"Test Chart\", \"data\": {\"x\": [\"A\", \"B\"], \"y\": [1, 2]}}"
        result3 = chart_tool.forward(json_escaped)
        
        success_count = sum(1 for r in [result1, result2, result3] if r.get('status') == 'success')
        return success_count >= 2  # At least 2 of 3 should work
    
    def test_malformed_json_recovery(self):
        """Test recovery from malformed JSON."""
        excel_tool = ExcelGeneratorTool()
        
        # Test cases with various JSON issues
        test_cases = [
            # Trailing comma
            '{"sheets": [{"name": "Test", "tables": [],}]}',
            # Missing quotes
            '{sheets: [{name: "Test", tables: []}]}',
            # Single quotes with internal quotes
            "{'sheets': [{'name': 'Test's Sheet', 'tables': []}]}",
            # Completely malformed
            'definitely not json',
            # Empty string
            '',
            # Just braces
            '{}',
        ]
        
        success_count = 0
        for test_json in test_cases:
            try:
                result = excel_tool.forward(test_json, "test_file")
                # Should either succeed or give helpful error message
                if isinstance(result, str) and ("successfully" in result or "Error" in result or "example" in result):
                    success_count += 1
            except Exception as e:
                print(f"Unexpected exception for '{test_json[:30]}...': {e}")
        
        return success_count >= len(test_cases) // 2  # At least half should be handled gracefully
    
    def test_empty_data_scenarios(self):
        """Test handling of empty or missing data."""
        excel_tool = ExcelGeneratorTool()
        
        # Test empty sheets
        empty_sheets = '{"sheets": []}'
        result1 = excel_tool.forward(empty_sheets, "empty_test")
        
        # Test sheets with no data
        no_data = '{"sheets": [{"name": "Empty", "tables": []}]}'
        result2 = excel_tool.forward(no_data, "no_data_test")
        
        # Test sheets with empty table data
        empty_tables = '{"sheets": [{"name": "Test", "tables": [{"data": []}]}]}'
        result3 = excel_tool.forward(empty_tables, "empty_tables_test")
        
        # All should complete without crashing and create some kind of file
        results = [result1, result2, result3]
        success_count = sum(1 for r in results if isinstance(r, str) and ("successfully" in r or "empty" in r))
        
        return success_count == 3
    
    def test_special_characters_handling(self):
        """Test handling of special characters and unicode."""
        word_tool = SimpleWordGeneratorTool()
        
        # Test with special characters
        special_content = """
        # Тест with Unicode: 你好世界
        
        Special chars: áéíóú ñ ç €£¥ 
        
        **Bold with émojis**: 🚀 💻 📊
        
        Code with symbols: `var price = $19.99;`
        """
        
        result = word_tool.forward(
            title="Special Characters Test 📝",
            content=special_content,
            filename="special_chars_test"
        )
        
        return isinstance(result, str) and "successfully" in result
    
    def test_large_data_handling(self):
        """Test handling of large datasets."""
        excel_tool = ExcelGeneratorTool()
        
        # Generate large dataset
        large_data = [["ID", "Name", "Value", "Category"]]
        for i in range(1000):
            large_data.append([f"ID{i:04d}", f"Item {i}", i * 1.5, f"Cat{i % 10}"])
        
        large_structure = {
            "sheets": [{
                "name": "Large Dataset",
                "tables": [{
                    "title": "1000 Row Dataset",
                    "data": large_data
                }]
            }]
        }
        
        result = excel_tool.forward(json.dumps(large_structure), "large_data_test")
        
        # Should handle large data without crashing
        return isinstance(result, str) and ("successfully" in result or "Error" in result)
    
    def test_data_type_variations(self):
        """Test various data types in Excel data."""
        excel_tool = ExcelGeneratorTool()
        
        # Mixed data types
        mixed_data = [
            ["String", "Integer", "Float", "Boolean", "Date", "None"],
            ["Hello", 42, 3.14159, True, "2024-01-01", None],
            ["World", -17, 0.0, False, "2024-12-31", ""],
            ["Test", "123", "45.67", "true", "invalid-date", "null"]
        ]
        
        mixed_structure = {
            "sheets": [{
                "name": "Mixed Types",
                "tables": [{
                    "data": mixed_data
                }]
            }]
        }
        
        result = excel_tool.forward(json.dumps(mixed_structure), "mixed_types_test")
        return isinstance(result, str) and "successfully" in result
    
    def test_chart_data_validation(self):
        """Test chart generation with invalid data configurations."""
        chart_tool = GenerateChartTool()
        
        test_cases = [
            # Missing required fields
            '{"type": "bar"}',
            # Mismatched x/y arrays
            '{"type": "bar", "data": {"x": ["A", "B"], "y": [1, 2, 3]}}',
            # Wrong data format for pie chart
            '{"type": "pie", "data": {"x": ["A", "B"], "y": [1, 2]}}',
            # Empty data arrays
            '{"type": "line", "data": {"x": [], "y": []}}',
            # Non-numeric y values
            '{"type": "bar", "data": {"x": ["A", "B"], "y": ["not", "numbers"]}}',
        ]
        
        success_count = 0
        for test_case in test_cases:
            result = chart_tool.forward(test_case)
            # Should handle gracefully with error message
            if isinstance(result, dict) and (result.get('status') == 'error' or result.get('status') == 'success'):
                success_count += 1
        
        return success_count == len(test_cases)
    
    def test_file_path_edge_cases(self):
        """Test file path handling edge cases."""
        modify_tool = ModifyExcelTool()
        
        # Test non-existent file
        result1 = modify_tool.forward(
            "nonexistent/path/file.xlsx",
            '{"operations": [{"type": "add_sheet", "name": "Test", "data": [["A", "B"], ["1", "2"]]}]}'
        )
        
        # Test empty file path
        result2 = modify_tool.forward(
            "",
            '{"operations": [{"type": "add_sheet", "name": "Test", "data": [["A", "B"], ["1", "2"]]}]}'
        )
        
        # Test path with spaces and special chars
        result3 = modify_tool.forward(
            "temp/my file (with spaces & chars).xlsx",
            '{"operations": [{"type": "add_sheet", "name": "Test", "data": [["A", "B"], ["1", "2"]]}]}'
        )
        
        # All should handle gracefully
        results = [result1, result2, result3]
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') in ['success', 'error'])
        
        return success_count == 3
    
    def test_artifact_edge_cases(self):
        """Test save artifact tool with edge cases."""
        artifact_tool = SaveArtifactTool()
        
        # Test empty content
        result1 = artifact_tool.forward("", "txt")
        
        # Test None content
        result2 = artifact_tool.forward(None, "txt")
        
        # Test invalid file type
        result3 = artifact_tool.forward("test content", "")
        
        # Test binary content
        result4 = artifact_tool.forward(b"binary content", "bin")
        
        # Test large content
        large_content = "Large content " * 10000
        result5 = artifact_tool.forward(large_content, "txt")
        
        # Should handle all cases gracefully
        results = [result1, result2, result3, result4, result5]
        handled_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') in ['success', 'error'])
        
        return handled_count == 5
    
    def test_concurrent_file_operations(self):
        """Test concurrent file creation scenarios."""
        excel_tool = ExcelGeneratorTool()
        
        # Create multiple files with same base name
        base_structure = '{"sheets": [{"name": "Test", "tables": [{"data": [["A"], ["1"]]}]}]}'
        
        results = []
        for i in range(5):
            result = excel_tool.forward(base_structure, f"concurrent_test_{i}")
            results.append(result)
        
        # All should succeed
        success_count = sum(1 for r in results if isinstance(r, str) and "successfully" in r)
        return success_count == 5
    
    def run_all_tests(self):
        """Run all test cases."""
        print("=" * 60)
        print("ROBUST SMOLAGENTS TOOLS TEST SUITE")
        print("=" * 60)
        
        # Define all tests
        tests = [
            ("JSON Quote Handling", self.test_json_quote_handling),
            ("Malformed JSON Recovery", self.test_malformed_json_recovery),
            ("Empty Data Scenarios", self.test_empty_data_scenarios),
            ("Special Characters Handling", self.test_special_characters_handling),
            ("Large Data Handling", self.test_large_data_handling),
            ("Data Type Variations", self.test_data_type_variations),
            ("Chart Data Validation", self.test_chart_data_validation),
            ("File Path Edge Cases", self.test_file_path_edge_cases),
            ("Artifact Edge Cases", self.test_artifact_edge_cases),
            ("Concurrent File Operations", self.test_concurrent_file_operations),
        ]
        
        # Run all tests
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = self.tests_passed + self.tests_failed
        print(f"Total tests: {total_tests}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Success rate: {(self.tests_passed/total_tests*100):.1f}%")
        
        # Print detailed results
        print("\nDetailed Results:")
        for test_name, status, error in self.test_results:
            if status == 'PASSED':
                print(f"✓ {test_name}")
            else:
                print(f"✗ {test_name}: {error}")
        
        if self.tests_failed == 0:
            print("\n🎉 ALL TESTS PASSED! Tools are robust and ready for production.")
        else:
            print(f"\n⚠️  {self.tests_failed} test(s) failed. Review and fix issues before deployment.")
        
        return self.tests_failed == 0

def main():
    """Run the robust tools test suite."""
    tester = RobustToolTests()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())