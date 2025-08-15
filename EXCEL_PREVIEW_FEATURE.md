# Excel Document Preview Feature

## Overview

The Excel Document Preview feature allows users to view the content of Excel spreadsheets directly in the chat interface without downloading them. This feature works similarly to the existing Word preview functionality but is specifically designed for Excel files (.xlsx and .xls formats).

## Features

- **Inline HTML Preview**: Excel spreadsheets are converted to HTML tables and displayed directly in the chat
- **Multi-sheet Support**: Navigate between different sheets using a tabbed interface
- **Expand/Collapse**: Users can toggle the preview visibility to save space
- **Full Window View**: Option to open the preview in a separate window for better readability
- **Automatic Generation**: Previews are automatically generated when Excel files are created, modified, or parsed
- **Data Truncation**: Large datasets are truncated to improve performance (first 100 rows per sheet)
- **Summary Statistics**: Display basic statistics about the spreadsheet (row count, column count, etc.)
- **Error Handling**: Graceful fallback when preview generation fails

## Technical Implementation

### Components

1. **ExcelPreviewGenerator** (`apps/agents/tools/excel_preview.py`)
   - Converts Excel spreadsheets to HTML tables using pandas
   - Supports both single and multi-sheet workbooks
   - Adds CSS classes for consistent styling
   - Truncates large datasets for performance
   - Generates tabbed interface for multi-sheet files

2. **Backend Views** (`apps/chat/views.py`)
   - `view_excel_preview` endpoint serves HTML previews
   - Includes security checks and session validation
   - Provides comprehensive CSS styling for Excel tables

3. **Frontend Template** (`templates/chat/partials/message.html`)
   - Detects Excel file artifacts based on file type and extension
   - Displays preview section with expand/collapse functionality
   - Includes loading indicators and error handling
   - Supports tabbed navigation for multi-sheet files

4. **JavaScript Functions**
   - `toggleExcelPreview()`: Expands/collapses preview
   - `openExcelPreviewWindow()`: Opens preview in new window
   - `hideExcelPreviewLoading()`: Manages loading states
   - `switchExcelTab()`: Switches between different sheets in multi-sheet files

5. **URL Configuration** (`apps/chat/urls.py`)
   - Added route: `preview/excel/<uuid:artifact_id>/`

### Integration Points

- **Excel Generator Tool**: Modified to generate previews after creating spreadsheets
- **Excel Modifier Tool**: Modified to generate previews after modifying spreadsheets
- **Parse Excel Tool**: Enhanced to generate previews when parsing existing Excel files
- **Orchestrator**: Enhanced to extract and store preview HTML in artifacts for Excel files

## Usage

### For Users

1. **Generate an Excel File**: Ask the AI to create an Excel spreadsheet
2. **Upload an Excel File**: Upload an existing Excel file for analysis
3. **View Preview**: The preview section appears automatically below the download button
4. **Expand Preview**: Click "Expand" to view the spreadsheet content inline
5. **Navigate Sheets**: For multi-sheet files, click tabs to switch between different sheets
6. **Full Window**: Click "Open" to view the preview in a separate window
7. **Download**: Use the download button to get the actual Excel file

### For Developers

#### Adding Preview Support to New Tools

```python
from apps.agents.tools.excel_preview import ExcelPreviewGenerator

# After saving an Excel file
preview_result = ExcelPreviewGenerator.generate_preview(file_path)
if preview_result['success']:
    preview_html = preview_result['preview_html']
    # Store preview_html in your result
```

#### Template Detection

Excel files are detected using:
```html
{% if "excel" in artifact.file_type or "spreadsheet" in artifact.file_type or artifact.file_name|lower|slice:"-5:" == ".xlsx" or artifact.file_name|lower|slice:"-4:" == ".xls" %}
    {% if artifact.preview_html %}
        <!-- Preview section -->
    {% endif %}
{% endif %}
```

## Configuration

### Requirements

- `pandas` library for Excel reading and HTML conversion
- `openpyxl` and `xlsxwriter` for Excel file handling
- Django database with `preview_html` field in Artifact model

### Settings

No additional settings required. The feature works out of the box with existing dependencies.

## Security Considerations

- **HTML Sanitization**: Preview HTML is cleaned to remove potentially dangerous content
- **Session Validation**: Preview endpoints validate user sessions
- **File Path Security**: Only files in allowed directories can be previewed
- **MIME Type Validation**: Only Excel documents are processed for previews

## Styling

The preview uses CSS classes for consistent styling:

- `.excel-sheet-container`: Container for individual sheets
- `.preview-sheet-title`: Sheet name headers
- `.excel-sheet-stats`: Summary statistics display
- `.preview-excel-table`: Main table styling
- `.preview-excel-header`: Table header cells
- `.preview-excel-cell`: Table data cells
- `.excel-tabs-container`: Multi-sheet tab interface
- `.excel-tab-button`: Individual tab buttons
- `.excel-tab-content`: Sheet content containers

## Error Handling

- **Generation Failures**: Graceful fallback when pandas conversion fails
- **Missing Files**: Appropriate error messages for missing documents
- **Invalid Documents**: Validation for corrupted or invalid Excel files
- **Empty Sheets**: Handles empty worksheets appropriately
- **Large Files**: Automatic truncation of large datasets

## Performance Considerations

- **Data Truncation**: Shows first 100 rows per sheet to improve loading times
- **Sheet Limit**: Processes maximum 10 sheets per workbook
- **Lazy Loading**: Previews are loaded only when expanded
- **Browser Caching**: Preview content is cached for better performance
- **Memory Management**: Temporary processing data is cleaned up appropriately

## Multi-Sheet Support

For Excel files with multiple sheets:
- Automatic detection of multiple sheets
- Tabbed interface for easy navigation
- JavaScript-powered sheet switching
- Individual statistics for each sheet
- Separate HTML content for each sheet

## Comparison with Word Preview

| Feature | Word Preview | Excel Preview |
|---------|-------------|---------------|
| File Types | .docx | .xlsx, .xls |
| Library Used | mammoth | pandas |
| Multi-Document Support | No | Yes (multi-sheet) |
| Navigation | Single view | Tabbed interface |
| Data Truncation | Text-based | Row-based (100 rows) |
| Statistics | None | Row/column counts |

## Future Enhancements

- **Chart Preview**: Display embedded charts from Excel files
- **Formula Display**: Show formulas in addition to values
- **Cell Formatting**: Preserve Excel formatting (colors, fonts, etc.)
- **Search Functionality**: Search within preview content
- **Export Options**: Export individual sheets as CSV
- **Advanced Filtering**: Filter and sort data within preview

## Troubleshooting

### Common Issues

1. **Preview Not Showing**
   - Check if pandas library is installed
   - Verify the file is a valid Excel document
   - Check browser console for JavaScript errors

2. **Multi-Sheet Navigation Issues**
   - Ensure JavaScript is enabled
   - Check for naming conflicts with sheet names

3. **Performance Issues**
   - Large files are automatically truncated
   - Consider file size limits for very large spreadsheets

4. **Styling Issues**
   - Ensure CSS classes are properly applied
   - Check for conflicting styles in custom CSS

### Debug Information

Enable debug logging to see preview generation details:
```python
import logging
logging.getLogger('apps.agents.tools.excel_preview').setLevel(logging.DEBUG)
```

## Testing

The feature has been tested with:
- Single-sheet Excel files
- Multi-sheet Excel files
- Various data types (text, numbers, dates)
- Empty sheets and files
- Large datasets (truncation verification)
- Different file extensions (.xlsx, .xls)

### Test Cases

1. **Basic Functionality**
   - Generate Excel file with simple data
   - Verify preview appears and is readable

2. **Multi-Sheet Support**
   - Create Excel file with multiple sheets
   - Verify tabbed interface works correctly

3. **Data Handling**
   - Test with various data types
   - Verify proper formatting and display

4. **Error Handling**
   - Test with corrupted Excel files
   - Test with missing dependencies

5. **Security**
   - Test preview access with different user sessions
   - Verify HTML sanitization works correctly