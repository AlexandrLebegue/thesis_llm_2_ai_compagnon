"""
Create a comprehensive dummy Microsoft Word document with sample data
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
from datetime import datetime


def create_comprehensive_dummy_document():
    """Create a comprehensive dummy Word document with various content types"""
    print("Creating comprehensive dummy Word document...")
    
    tool = ModifyWordTool()
    
    # Rich instruction set with various content types
    instructions = {
        "add_headings": [
            {"text": "Company Annual Report 2024", "level": 1},
            {"text": "Executive Summary", "level": 2},
            {"text": "Financial Performance", "level": 2},
            {"text": "Employee Information", "level": 2},
            {"text": "Product Portfolio", "level": 2},
            {"text": "Regional Sales Data", "level": 2}
        ],
        "add_paragraphs": [
            {"text": f"Document generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"},
            {"text": "This document contains comprehensive dummy data for demonstration purposes. All information presented here is purely fictional and created for testing and development purposes only."},
            {"text": ""},  # Empty paragraph for spacing
            {"text": "TechCorp Industries has shown remarkable growth this fiscal year, with revenue increasing by 23% compared to the previous year. Our innovative products and dedicated workforce have been the driving forces behind this success."},
            {"text": ""},
            {"text": "The following sections provide detailed insights into our company's performance across various departments and regions."},
            {"text": ""},
            {"text": "Our financial performance this year exceeded all expectations. The company achieved record-breaking profits while maintaining sustainable growth practices and investing heavily in research and development."},
            {"text": ""},
            {"text": "Our talented workforce continues to be our greatest asset. Below is the current breakdown of our employee base across different departments."},
            {"text": ""},
            {"text": "Our diverse product portfolio spans multiple market segments, ensuring stable revenue streams and reduced market risk."},
            {"text": ""},
            {"text": "Regional sales performance shows strong growth across all markets, with particularly impressive results in the Asia-Pacific region."}
        ],
        "add_tables": [
            {
                "data": [
                    ["Quarter", "Revenue ($M)", "Profit ($M)", "Growth (%)"],
                    ["Q1 2024", "125.5", "18.2", "15.3"],
                    ["Q2 2024", "142.8", "22.1", "18.7"],
                    ["Q3 2024", "156.3", "25.8", "21.2"],
                    ["Q4 2024", "178.9", "31.4", "23.1"],
                    ["Total 2024", "603.5", "97.5", "19.6"]
                ],
                "style": "Table Grid"
            },
            {
                "data": [
                    ["Employee ID", "Name", "Department", "Position", "Years", "Salary"],
                    ["EMP001", "Alice Johnson", "Engineering", "Senior Developer", "5", "$95,000"],
                    ["EMP002", "Bob Smith", "Marketing", "Marketing Manager", "3", "$78,000"],
                    ["EMP003", "Carol Davis", "Sales", "Sales Director", "7", "$105,000"],
                    ["EMP004", "David Wilson", "HR", "HR Specialist", "2", "$65,000"],
                    ["EMP005", "Emily Brown", "Finance", "Financial Analyst", "4", "$72,000"],
                    ["EMP006", "Frank Miller", "Engineering", "Tech Lead", "6", "$98,000"],
                    ["EMP007", "Grace Lee", "Marketing", "Content Creator", "1", "$55,000"],
                    ["EMP008", "Henry Taylor", "Sales", "Account Executive", "3", "$68,000"],
                    ["EMP009", "Isabel Garcia", "Operations", "Operations Manager", "8", "$88,000"],
                    ["EMP010", "Jack Anderson", "Engineering", "Junior Developer", "1", "$58,000"]
                ],
                "style": "Table Grid"
            },
            {
                "data": [
                    ["Product Name", "Category", "Units Sold", "Revenue ($K)", "Market Share (%)"],
                    ["TechWidget Pro", "Hardware", "15,420", "2,313", "12.5"],
                    ["CloudSync Enterprise", "Software", "8,750", "1,750", "8.3"],
                    ["DataAnalyzer Suite", "Analytics", "3,250", "1,625", "15.2"],
                    ["MobileApp Premium", "Mobile", "25,680", "1,284", "6.7"],
                    ["SecurityGuard Plus", "Security", "5,890", "2,356", "18.9"],
                    ["AutomationBot", "AI/ML", "2,150", "1,075", "22.1"]
                ],
                "style": "Table Grid"
            },
            {
                "data": [
                    ["Region", "Sales ($M)", "Growth (%)", "Market Penetration (%)", "Customer Count"],
                    ["North America", "245.8", "18.5", "35.2", "12,450"],
                    ["Europe", "185.2", "22.1", "28.7", "9,180"],
                    ["Asia-Pacific", "128.7", "31.4", "15.8", "15,630"],
                    ["Latin America", "32.1", "14.2", "8.1", "3,220"],
                    ["Middle East & Africa", "11.7", "45.8", "3.2", "1,840"]
                ],
                "style": "Table Grid"
            }
        ]
    }
    
    # Create the document
    result = tool.forward(
        file_path="comprehensive_dummy_document.docx",
        instructions=json.dumps(instructions)
    )
    
    print(f"Document Creation Result: {result}")
    
    if result.get('status') == 'success':
        output_path = result.get('output_path')
        if output_path and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Comprehensive document created successfully!")
            print(f"  Location: {output_path}")
            print(f"  File size: {file_size:,} bytes")
            print(f"  Document contains:")
            print(f"    - 6 headings")
            print(f"    - 13 paragraphs")
            print(f"    - 4 data tables")
            print(f"    - Financial performance data")
            print(f"    - Employee information")
            print(f"    - Product portfolio details")
            print(f"    - Regional sales analysis")
        else:
            print(f"✗ Document file not found: {output_path}")
    else:
        print(f"✗ Document creation failed: {result}")
    
    print("\nComprehensive dummy Word document creation completed!")


if __name__ == "__main__":
    create_comprehensive_dummy_document()