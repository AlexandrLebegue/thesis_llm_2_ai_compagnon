"""
Test script to verify Excel document creation functionality
"""
import os
import sys
import django

# Setup Django
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

from apps.agents.tools.modify_excel_tool import ModifyExcelTool
import json


def test_excel_creation():
    """Test Excel document creation with dummy data"""
    print("Testing Excel document creation...")
    
    tool = ModifyExcelTool()
    
    # Test data with flexible instruction format
    instructions = {
        "add_sheets": [
            {
                "name": "Financial Data",
                "data": [
                    ["Quarter", "Revenue ($M)", "Profit ($M)", "Growth (%)"],
                    ["Q1 2024", "125.5", "18.2", "15.3"],
                    ["Q2 2024", "142.8", "22.1", "18.7"],
                    ["Q3 2024", "156.3", "25.8", "21.2"],
                    ["Q4 2024", "178.9", "31.4", "23.1"]
                ]
            },
            {
                "name": "Employee Data",
                "data": [
                    ["Employee ID", "Name", "Department", "Position", "Salary"],
                    ["EMP001", "Alice Johnson", "Engineering", "Senior Developer", "$95,000"],
                    ["EMP002", "Bob Smith", "Marketing", "Marketing Manager", "$78,000"],
                    ["EMP003", "Carol Davis", "Sales", "Sales Director", "$105,000"],
                    ["EMP004", "David Wilson", "HR", "HR Specialist", "$65,000"],
                    ["EMP005", "Emily Brown", "Finance", "Financial Analyst", "$72,000"]
                ]
            },
            {
                "name": "Product Sales",
                "data": [
                    ["Product Name", "Units Sold", "Revenue ($K)", "Market Share (%)"],
                    ["TechWidget Pro", "15,420", "2,313", "12.5"],
                    ["CloudSync Enterprise", "8,750", "1,750", "8.3"],
                    ["DataAnalyzer Suite", "3,250", "1,625", "15.2"],
                    ["MobileApp Premium", "25,680", "1,284", "6.7"],
                    ["SecurityGuard Plus", "5,890", "2,356", "18.9"]
                ]
            }
        ]
    }
    
    # Test 1: Create new Excel file with flexible format
    result = tool.forward(
        file_path="dummy_spreadsheet.xlsx",
        instructions=json.dumps(instructions)
    )
    
    print(f"Test 1 Result: {result}")
    
    if result.get('status') == 'success':
        output_path = result.get('output_path')
        if output_path and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Excel file created successfully: {output_path}")
            print(f"  File size: {file_size} bytes")
        else:
            print(f"✗ Excel file not found: {output_path}")
    else:
        print(f"✗ Excel file creation failed: {result}")
    
    # Test 2: Create Excel file with operations format
    operations_instructions = {
        "operations": [
            {
                "type": "add_sheet",
                "name": "Sales Summary",
                "data": [
                    ["Region", "Sales ($M)", "Growth (%)", "Customer Count"],
                    ["North America", "245.8", "18.5", "12,450"],
                    ["Europe", "185.2", "22.1", "9,180"],
                    ["Asia-Pacific", "128.7", "31.4", "15,630"],
                    ["Latin America", "32.1", "14.2", "3,220"]
                ]
            },
            {
                "type": "add_sheet",
                "name": "Budget Analysis", 
                "data": [
                    ["Department", "Budget ($K)", "Spent ($K)", "Remaining ($K)", "Utilization (%)"],
                    ["Engineering", "500", "420", "80", "84.0"],
                    ["Marketing", "300", "275", "25", "91.7"],
                    ["Sales", "200", "185", "15", "92.5"],
                    ["HR", "150", "135", "15", "90.0"],
                    ["Operations", "250", "230", "20", "92.0"]
                ]
            }
        ]
    }
    
    result2 = tool.forward(
        file_path="operations_excel_test.xlsx",
        instructions=json.dumps(operations_instructions)
    )
    
    print(f"\nTest 2 Result: {result2}")
    
    if result2.get('status') == 'success':
        output_path2 = result2.get('output_path')
        if output_path2 and os.path.exists(output_path2):
            file_size2 = os.path.getsize(output_path2)
            print(f"✓ Operations Excel file created successfully: {output_path2}")
            print(f"  File size: {file_size2} bytes")
        else:
            print(f"✗ Operations Excel file not found: {output_path2}")
    else:
        print(f"✗ Operations Excel file creation failed: {result2}")
    
    print("\nExcel document creation tests completed!")


if __name__ == "__main__":
    test_excel_creation()