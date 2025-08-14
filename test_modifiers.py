"""
Test script for document modification tools
"""
import os
import sys
import django
from pathlib import Path
import traceback

# Setup Django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')
django.setup()

from apps.agents.tools.excel_modifier import ExcelModifier
from apps.agents.tools.word_modifier import WordModifier
from apps.agents.tools.chart_generator import ChartGenerator

def test_excel_modifier():
    """Test Excel modification functionality"""
    print("=" * 50)
    print("TESTING EXCEL MODIFIER")
    print("=" * 50)
    
    try:
        # Test 1: Basic modification with data and chart
        print("\n1. Testing Excel modification with data and chart...")
        
        # Instructions for Excel modification
        excel_instructions = {
            'operations': [
                {
                    'type': 'add_sheet',
                    'name': 'Analytics'
                },
                {
                    'type': 'add_data',
                    'sheet': 'Sheet1',
                    'data': [
                        ['Quarter', 'Sales', 'Profit'],
                        ['Q1', 10000, 2000],
                        ['Q2', 15000, 3500],
                        ['Q3', 12000, 2800],
                        ['Q4', 18000, 4200]
                    ]
                },
                {
                    'type': 'add_chart',
                    'sheet': 'Sheet1',
                    'chart_type': 'column',
                    'title': 'Quarterly Sales Performance',
                    'categories_range': '=Sheet1!$A$2:$A$5',
                    'values_range': '=Sheet1!$B$2:$B$5',
                    'x_axis_label': 'Quarter',
                    'y_axis_label': 'Sales ($)',
                    'position': 'E2'
                },
                {
                    'type': 'add_formula',
                    'sheet': 'Sheet1',
                    'cell': 'B6',
                    'formula': '=SUM(B2:B5)'
                }
            ]
        }
        
        output_path = ExcelModifier.modify_excel(
            'test_files/sample.xlsx',
            excel_instructions
        )
        print(f"✅ Excel modification successful: {output_path}")
        
        # Test 2: Different chart types
        print("\n2. Testing different chart types...")
        chart_instructions = {
            'operations': [
                {
                    'type': 'add_chart',
                    'sheet': 'Sheet1',
                    'chart_type': 'pie',
                    'title': 'Sales Distribution',
                    'categories_range': '=Sheet1!$A$2:$A$5',
                    'values_range': '=Sheet1!$B$2:$B$5',
                    'position': 'E15'
                }
            ]
        }
        
        output_path2 = ExcelModifier.modify_excel(
            output_path,
            chart_instructions
        )
        print(f"✅ Chart addition successful: {output_path2}")
        
    except Exception as e:
        print(f"❌ Excel modifier test failed: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

def test_word_modifier():
    """Test Word modification functionality"""
    print("\n" + "=" * 50)
    print("TESTING WORD MODIFIER")
    print("=" * 50)
    
    try:
        # Generate a sample chart first for image insertion
        print("\n1. Generating sample chart for insertion...")
        chart_data = {
            'x': ['Jan', 'Feb', 'Mar', 'Apr'],
            'y': [20, 35, 30, 45]
        }
        chart_path = ChartGenerator.generate_chart(
            chart_data,
            chart_type='bar',
            title='Monthly Progress',
            xlabel='Month',
            ylabel='Progress (%)'
        )
        print(f"✅ Chart generated: {chart_path}")
        
        # Test Word modification
        print("\n2. Testing Word modification with content and table...")
        
        word_instructions = {
            'operations': [
                {
                    'type': 'add_heading',
                    'text': 'Monthly Report',
                    'level': 1
                },
                {
                    'type': 'add_paragraph',
                    'text': 'This document contains our monthly performance analysis.',
                    'bold': True
                },
                {
                    'type': 'add_heading',
                    'text': 'Performance Data',
                    'level': 2
                },
                {
                    'type': 'add_table',
                    'headers': ['Month', 'Target', 'Actual', 'Variance'],
                    'data': [
                        ['January', '100', '110', '+10'],
                        ['February', '120', '115', '-5'],
                        ['March', '110', '125', '+15'],
                        ['April', '130', '135', '+5']
                    ]
                },
                {
                    'type': 'add_paragraph',
                    'text': 'The chart below shows our monthly progress:',
                    'alignment': 'center'
                },
                {
                    'type': 'insert_image',
                    'image_index': 0,
                    'width': 5
                },
                {
                    'type': 'add_page_break'
                },
                {
                    'type': 'add_heading',
                    'text': 'Conclusion',
                    'level': 2
                },
                {
                    'type': 'add_paragraph',
                    'text': 'Overall performance has been positive with consistent growth.',
                    'italic': True
                }
            ]
        }
        
        output_path = WordModifier.modify_word(
            'test_files/sample.docx',
            word_instructions,
            images=[chart_path]
        )
        print(f"✅ Word modification successful: {output_path}")
        
    except Exception as e:
        print(f"❌ Word modifier test failed: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

def test_chart_integration():
    """Test integration with chart generator"""
    print("\n" + "=" * 50)
    print("TESTING CHART INTEGRATION")
    print("=" * 50)
    
    try:
        # Test 1: Generate different chart types
        print("\n1. Testing different chart types...")
        
        sample_data = {
            'x': ['Product A', 'Product B', 'Product C', 'Product D'],
            'y': [23, 45, 56, 78]
        }
        
        chart_types = ['bar', 'line', 'pie', 'scatter']
        chart_paths = []
        
        for chart_type in chart_types:
            try:
                path = ChartGenerator.generate_chart(
                    sample_data,
                    chart_type=chart_type,
                    title=f'{chart_type.title()} Chart Example',
                    xlabel='Products',
                    ylabel='Sales'
                )
                chart_paths.append(path)
                print(f"✅ {chart_type} chart generated: {path}")
            except Exception as e:
                print(f"❌ {chart_type} chart failed: {str(e)}")
        
        # Test 2: Use charts in Word document
        print("\n2. Testing chart integration in Word document...")
        
        word_instructions = {
            'operations': [
                {
                    'type': 'add_heading',
                    'text': 'Chart Gallery',
                    'level': 1
                }
            ]
        }
        
        # Add each chart to the document
        for i, chart_path in enumerate(chart_paths):
            word_instructions['operations'].extend([
                {
                    'type': 'add_heading',
                    'text': f'Chart {i+1}: {chart_types[i].title()}',
                    'level': 2
                },
                {
                    'type': 'insert_image',
                    'image_index': i,
                    'width': 4
                },
                {
                    'type': 'add_paragraph',
                    'text': f'This is a {chart_types[i]} chart showing product sales data.'
                }
            ])
        
        output_path = WordModifier.modify_word(
            None,  # Create new document
            word_instructions,
            images=chart_paths
        )
        print(f"✅ Chart integration successful: {output_path}")
        
    except Exception as e:
        print(f"❌ Chart integration test failed: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

def test_error_handling():
    """Test error handling and edge cases"""
    print("\n" + "=" * 50)
    print("TESTING ERROR HANDLING")
    print("=" * 50)
    
    try:
        # Test 1: Invalid file path
        print("\n1. Testing invalid file path...")
        try:
            ExcelModifier.modify_excel(
                'nonexistent/file.xlsx',
                {'operations': []}
            )
            print("❌ Should have failed with invalid file path")
            return False
        except Exception as e:
            print(f"✅ Correctly handled invalid file path: {type(e).__name__}")
        
        # Test 2: Invalid chart type
        print("\n2. Testing invalid chart type...")
        try:
            ChartGenerator.generate_chart(
                {'x': [1, 2, 3], 'y': [1, 2, 3]},
                chart_type='invalid_type'
            )
            print("❌ Should have failed with invalid chart type")
            return False
        except ValueError as e:
            print(f"✅ Correctly handled invalid chart type: {str(e)}")
        
        # Test 3: Empty operations
        print("\n3. Testing empty operations...")
        try:
            output_path = WordModifier.modify_word(
                None,
                {'operations': []},
                images=[]
            )
            print(f"✅ Handled empty operations: {output_path}")
        except Exception as e:
            print(f"❌ Failed to handle empty operations: {str(e)}")
            return False
        
    except Exception as e:
        print(f"❌ Error handling test failed: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

def main():
    """Run all tests"""
    print("ULTRA PDF CHATBOT 3000 - Document Modifier Tests")
    print("=" * 60)
    
    # Create output directories
    Path('/tmp/ultra_pdf_chatbot/outputs').mkdir(parents=True, exist_ok=True)
    Path('/tmp/ultra_pdf_chatbot/charts').mkdir(parents=True, exist_ok=True)
    
    tests = [
        ("Excel Modifier", test_excel_modifier),
        ("Word Modifier", test_word_modifier),
        ("Chart Integration", test_chart_integration),
        ("Error Handling", test_error_handling)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} tests...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test suite failed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nOverall: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All tests passed! Document modifiers are working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the output above.")

if __name__ == '__main__':
    main()