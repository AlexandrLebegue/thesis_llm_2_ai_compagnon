"""
Create a comprehensive dummy Microsoft Excel document with sample data
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
from datetime import datetime


def create_comprehensive_dummy_excel():
    """Create a comprehensive dummy Excel document with various data types"""
    print("Creating comprehensive dummy Excel document...")
    
    tool = ModifyExcelTool()
    
    # Rich instruction set with multiple sheets and various data types
    instructions = {
        "add_sheets": [
            {
                "name": "Financial Summary",
                "data": [
                    ["Metric", "Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", "YTD Total"],
                    ["Revenue ($M)", "125.5", "142.8", "156.3", "178.9", "603.5"],
                    ["Profit ($M)", "18.2", "22.1", "25.8", "31.4", "97.5"],
                    ["Growth (%)", "15.3", "18.7", "21.2", "23.1", "19.6"],
                    ["Operating Margin (%)", "14.5", "15.5", "16.5", "17.6", "16.0"],
                    ["Cash Flow ($M)", "22.3", "28.1", "32.5", "38.7", "121.6"],
                    ["EBITDA ($M)", "25.1", "30.2", "34.8", "42.1", "132.2"]
                ]
            },
            {
                "name": "Employee Directory",
                "data": [
                    ["ID", "First Name", "Last Name", "Department", "Position", "Hire Date", "Salary", "Email"],
                    ["EMP001", "Alice", "Johnson", "Engineering", "Senior Developer", "2019-03-15", "$95,000", "alice.johnson@company.com"],
                    ["EMP002", "Bob", "Smith", "Marketing", "Marketing Manager", "2021-07-10", "$78,000", "bob.smith@company.com"],
                    ["EMP003", "Carol", "Davis", "Sales", "Sales Director", "2017-11-20", "$105,000", "carol.davis@company.com"],
                    ["EMP004", "David", "Wilson", "HR", "HR Specialist", "2022-01-08", "$65,000", "david.wilson@company.com"],
                    ["EMP005", "Emily", "Brown", "Finance", "Financial Analyst", "2020-05-22", "$72,000", "emily.brown@company.com"],
                    ["EMP006", "Frank", "Miller", "Engineering", "Tech Lead", "2018-09-12", "$98,000", "frank.miller@company.com"],
                    ["EMP007", "Grace", "Lee", "Marketing", "Content Creator", "2023-02-14", "$55,000", "grace.lee@company.com"],
                    ["EMP008", "Henry", "Taylor", "Sales", "Account Executive", "2021-08-30", "$68,000", "henry.taylor@company.com"],
                    ["EMP009", "Isabel", "Garcia", "Operations", "Operations Manager", "2016-04-18", "$88,000", "isabel.garcia@company.com"],
                    ["EMP010", "Jack", "Anderson", "Engineering", "Junior Developer", "2023-06-05", "$58,000", "jack.anderson@company.com"],
                    ["EMP011", "Karen", "White", "Finance", "Controller", "2019-12-01", "$92,000", "karen.white@company.com"],
                    ["EMP012", "Luke", "Thomas", "Sales", "Sales Rep", "2022-03-10", "$62,000", "luke.thomas@company.com"]
                ]
            },
            {
                "name": "Product Portfolio",
                "data": [
                    ["Product ID", "Product Name", "Category", "Launch Date", "Units Sold", "Revenue ($K)", "Cost ($K)", "Profit ($K)", "Market Share (%)"],
                    ["PRD001", "TechWidget Pro", "Hardware", "2022-01-15", "15,420", "2,313", "1,542", "771", "12.5"],
                    ["PRD002", "CloudSync Enterprise", "Software", "2021-06-20", "8,750", "1,750", "875", "875", "8.3"],
                    ["PRD003", "DataAnalyzer Suite", "Analytics", "2020-11-10", "3,250", "1,625", "650", "975", "15.2"],
                    ["PRD004", "MobileApp Premium", "Mobile", "2023-03-05", "25,680", "1,284", "770", "514", "6.7"],
                    ["PRD005", "SecurityGuard Plus", "Security", "2019-08-30", "5,890", "2,356", "1,178", "1,178", "18.9"],
                    ["PRD006", "AutomationBot", "AI/ML", "2023-09-12", "2,150", "1,075", "430", "645", "22.1"],
                    ["PRD007", "WebBuilder Pro", "Development", "2022-04-18", "12,340", "1,851", "926", "925", "9.8"],
                    ["PRD008", "CRM Manager", "Business", "2021-12-03", "7,890", "1,973", "790", "1,183", "14.3"]
                ]
            },
            {
                "name": "Regional Sales",
                "data": [
                    ["Region", "Country", "Sales Rep", "Q1 Sales ($M)", "Q2 Sales ($M)", "Q3 Sales ($M)", "Q4 Sales ($M)", "Total ($M)", "Growth (%)", "Customers"],
                    ["North America", "USA", "Carol Davis", "180.5", "195.2", "208.8", "225.3", "809.8", "18.5", "8,950"],
                    ["North America", "Canada", "Henry Taylor", "32.8", "35.1", "38.4", "42.2", "148.5", "22.1", "2,180"],
                    ["North America", "Mexico", "Luke Thomas", "12.5", "14.2", "15.8", "17.4", "59.9", "16.8", "1,320"],
                    ["Europe", "Germany", "Emily Brown", "45.8", "52.3", "58.1", "64.2", "220.4", "25.3", "3,240"],
                    ["Europe", "UK", "Frank Miller", "38.2", "41.5", "45.8", "50.1", "175.6", "19.7", "2,680"],
                    ["Europe", "France", "Grace Lee", "28.7", "31.2", "34.5", "38.8", "133.2", "21.4", "1,950"],
                    ["Asia-Pacific", "Japan", "Isabel Garcia", "25.4", "29.8", "34.2", "39.1", "128.5", "28.9", "4,120"],
                    ["Asia-Pacific", "Australia", "Jack Anderson", "18.9", "21.3", "24.7", "28.4", "93.3", "24.6", "1,890"],
                    ["Asia-Pacific", "Singapore", "Karen White", "15.2", "18.1", "21.8", "26.2", "81.3", "31.2", "2,340"],
                    ["Latin America", "Brazil", "Bob Smith", "22.1", "24.8", "27.5", "30.9", "105.3", "19.8", "2,680"],
                    ["Latin America", "Argentina", "David Wilson", "8.4", "9.7", "11.2", "12.8", "42.1", "23.5", "980"]
                ]
            },
            {
                "name": "Inventory Status",
                "data": [
                    ["SKU", "Product", "Warehouse", "Current Stock", "Min Stock", "Max Stock", "Reorder Point", "Status", "Last Updated"],
                    ["SKU001", "TechWidget Pro", "Warehouse A", "2,450", "500", "5,000", "750", "Normal", "2024-12-10"],
                    ["SKU002", "CloudSync Enterprise", "Warehouse B", "890", "200", "2,000", "300", "Normal", "2024-12-09"],
                    ["SKU003", "DataAnalyzer Suite", "Warehouse A", "150", "100", "1,000", "200", "Low Stock", "2024-12-08"],
                    ["SKU004", "MobileApp Premium", "Warehouse C", "3,240", "800", "6,000", "1,200", "Normal", "2024-12-10"],
                    ["SKU005", "SecurityGuard Plus", "Warehouse B", "680", "300", "2,500", "450", "Normal", "2024-12-07"],
                    ["SKU006", "AutomationBot", "Warehouse A", "85", "50", "500", "100", "Low Stock", "2024-12-06"],
                    ["SKU007", "WebBuilder Pro", "Warehouse C", "1,890", "400", "4,000", "600", "Normal", "2024-12-09"],
                    ["SKU008", "CRM Manager", "Warehouse B", "425", "150", "1,500", "250", "Normal", "2024-12-08"]
                ]
            },
            {
                "name": "Customer Analytics",
                "data": [
                    ["Customer ID", "Company Name", "Industry", "Total Purchases ($K)", "Last Purchase", "Status", "Account Manager", "Region"],
                    ["CUS001", "TechCorp Solutions", "Technology", "450.2", "2024-11-28", "Active", "Carol Davis", "North America"],
                    ["CUS002", "Global Manufacturing", "Manufacturing", "389.7", "2024-12-05", "Active", "Henry Taylor", "North America"],
                    ["CUS003", "FinanceFirst Bank", "Financial", "567.8", "2024-11-15", "Active", "Emily Brown", "Europe"],
                    ["CUS004", "HealthCare Plus", "Healthcare", "234.5", "2024-12-01", "Active", "Frank Miller", "Europe"],
                    ["CUS005", "RetailMax Chain", "Retail", "789.3", "2024-11-22", "Active", "Isabel Garcia", "Asia-Pacific"],
                    ["CUS006", "EduLearn Institute", "Education", "123.8", "2024-10-18", "Inactive", "Jack Anderson", "Asia-Pacific"],
                    ["CUS007", "Construction Build", "Construction", "345.6", "2024-12-03", "Active", "Bob Smith", "Latin America"],
                    ["CUS008", "Energy Solutions", "Energy", "678.9", "2024-11-30", "Active", "David Wilson", "Latin America"],
                    ["CUS009", "Media & Entertainment", "Media", "456.1", "2024-12-07", "Active", "Grace Lee", "Europe"],
                    ["CUS010", "Logistics Express", "Logistics", "567.4", "2024-11-25", "Active", "Luke Thomas", "North America"]
                ]
            }
        ]
    }
    
    # Create the Excel document
    result = tool.forward(
        file_path="comprehensive_dummy_spreadsheet.xlsx",
        instructions=json.dumps(instructions)
    )
    
    print(f"Document Creation Result: {result}")
    
    if result.get('status') == 'success':
        output_path = result.get('output_path')
        if output_path and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Comprehensive Excel document created successfully!")
            print(f"  Location: {output_path}")
            print(f"  File size: {file_size:,} bytes")
            print(f"  Document contains 6 worksheets:")
            print(f"    - Financial Summary (quarterly performance metrics)")
            print(f"    - Employee Directory (12 employees with contact info)")
            print(f"    - Product Portfolio (8 products with sales data)")
            print(f"    - Regional Sales (11 regions with detailed breakdown)")
            print(f"    - Inventory Status (8 products with stock levels)")
            print(f"    - Customer Analytics (10 major customers with purchase data)")
        else:
            print(f"✗ Document file not found: {output_path}")
    else:
        print(f"✗ Document creation failed: {result}")
    
    print(f"\nDocument generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    print("Comprehensive dummy Excel document creation completed!")


if __name__ == "__main__":
    create_comprehensive_dummy_excel()