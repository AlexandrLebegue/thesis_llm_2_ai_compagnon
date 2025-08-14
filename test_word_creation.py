"""
Test script to verify Word document creation functionality
"""
import os
import sys
import django

# Setup Django
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

from apps.agents.tools.modify_word_tool import ModifyWordTool
import json


def test_word_creation():
    """Test Word document creation with dummy data"""
    print("Testing Word document creation...")
    
    tool = ModifyWordTool()
    
    # Test data with flexible instruction format
    instructions = {
        "add_headings": [
            {"text": "Dummy Document with Sample Data", "level": 1}
        ],
        "add_paragraphs": [
            {"text": "This document contains dummy data for demonstration purposes."},
            {"text": "The information below is purely fictional and created for testing."}
        ],
        "add_tables": [
            {
                "data": [
                    ["Name", "Age", "Department"],
                    ["John Doe", "35", "Marketing"],
                    ["Jane Smith", "28", "Finance"],
                    ["Robert Johnson", "42", "IT"],
                    ["Sarah Williams", "31", "Human Resources"]
                ],
                "style": "Table Grid"
            }
        ]
    }
    
    # Test 1: Create new document with flexible format
    result = tool.forward(
        file_path="dummy_document.docx",
        instructions=json.dumps(instructions)
    )
    
    print(f"Test 1 Result: {result}")
    
    if result.get('status') == 'success':
        output_path = result.get('output_path')
        if output_path and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Document created successfully: {output_path}")
            print(f"  File size: {file_size} bytes")
        else:
            print(f"✗ Document file not found: {output_path}")
    else:
        print(f"✗ Document creation failed: {result}")
    
    # Test 2: Create document with operations format
    operations_instructions = {
        "operations": [
            {"type": "add_heading", "text": "Operations Format Test", "level": 1},
            {"type": "add_paragraph", "text": "This document was created using the operations format."},
            {"type": "add_table", "data": [
                ["Product", "Price", "Stock"],
                ["Laptop", "$999", "15"],
                ["Mouse", "$25", "50"],
                ["Keyboard", "$75", "30"]
            ], "style": "Table Grid"}
        ]
    }
    
    result2 = tool.forward(
        file_path="operations_test.docx",
        instructions=json.dumps(operations_instructions)
    )
    
    print(f"\nTest 2 Result: {result2}")
    
    if result2.get('status') == 'success':
        output_path2 = result2.get('output_path')
        if output_path2 and os.path.exists(output_path2):
            file_size2 = os.path.getsize(output_path2)
            print(f"✓ Operations document created successfully: {output_path2}")
            print(f"  File size: {file_size2} bytes")
        else:
            print(f"✗ Operations document file not found: {output_path2}")
    else:
        print(f"✗ Operations document creation failed: {result2}")
    
    print("\nWord document creation tests completed!")


if __name__ == "__main__":
    test_word_creation()