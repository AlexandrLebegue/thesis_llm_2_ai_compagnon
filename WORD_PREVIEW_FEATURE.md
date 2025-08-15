# Word Document Preview Feature

## Overview

The Word Document Preview feature allows users to view the content of generated Word documents directly in the chat interface without downloading them. This feature works similarly to the existing chart preview functionality but is specifically designed for Word documents.

## Features

- **Inline HTML Preview**: Word documents are converted to HTML and displayed directly in the chat
- **Expand/Collapse**: Users can toggle the preview visibility to save space
- **Full Window View**: Option to open the preview in a separate window for better readability
- **Automatic Generation**: Previews are automatically generated when Word documents are created or modified
- **Error Handling**: Graceful fallback when preview generation fails

## Technical Implementation

### Components

1. **WordPreviewGenerator** (`apps/agents/tools/word_preview.py`)
   - Converts Word documents to HTML using the mammoth library
   - Sanitizes HTML content for safe display
   - Adds CSS classes for consistent styling

2. **Database Model** (`apps/chat/models.py`)
   - Added `preview_html` field to the `Artifact` model
   - Stores the generated HTML preview content

3. **Backend Views** (`apps/chat/views.py`)
   - `view_word_preview` endpoint serves HTML previews
   - Includes security checks and session validation

4. **Frontend Template** (`templates/chat/partials/message.html`)
   - Detects Word document artifacts
   - Displays preview section with expand/collapse functionality
   - Includes loading indicators and error handling

5. **JavaScript Functions**
   - `toggleWordPreview()`: Expands/collapses preview
   - `openWordPreviewWindow()`: Opens preview in new window
   - `hideWordPreviewLoading()`: Manages loading states

### Integration Points

- **Word Generator Tool**: Modified to generate previews after creating documents
- **Word Modifier Tool**: Modified to generate previews after modifying documents
- **Orchestrator**: Enhanced to extract and store preview HTML in artifacts

## Usage

### For Users

1. **Generate a Word Document**: Ask the AI to create a Word document
2. **View Preview**: The preview section appears automatically below the download button
3. **Expand Preview**: Click "Expand" to view the document content inline
4. **Full Window**: Click "Open" to view the preview in a separate window
5. **Download**: Use the download button to get the actual Word file

### For Developers

#### Adding Preview Support to New Tools

```python
from apps.agents.tools.word_preview import WordPreviewGenerator

# After saving a Word document
preview_result = WordPreviewGenerator.generate_preview(file_path)
if preview_result['success']:
    preview_html = preview_result['preview_html']
    # Store preview_html in your result
```

#### Template Detection

Word documents are detected using:
```html
{% if "word" in artifact.file_type or artifact.file_name|lower|slice:"-5:" == ".docx" %}
    {% if artifact.preview_html %}
        <!-- Preview section -->
    {% endif %}
{% endif %}
```

## Configuration

### Requirements

- `mammoth==1.6.0` library for Word-to-HTML conversion
- Django database migration for `preview_html` field

### Settings

No additional settings required. The feature works out of the box once dependencies are installed.

## Security Considerations

- **HTML Sanitization**: Preview HTML is cleaned to remove potentially dangerous content
- **Session Validation**: Preview endpoints validate user sessions
- **File Path Security**: Only files in allowed directories can be previewed
- **MIME Type Validation**: Only Word documents are processed for previews

## Styling

The preview uses CSS classes for consistent styling:

- `.preview-h1`, `.preview-h2`, etc.: Heading styles
- `.preview-paragraph`: Paragraph formatting
- `.preview-table`: Table styling
- `.preview-list`: List formatting
- `.preview-quote`: Blockquote styling

## Error Handling

- **Generation Failures**: Graceful fallback when mammoth conversion fails
- **Missing Files**: Appropriate error messages for missing documents
- **Import Errors**: Safe handling when mammoth library is not available
- **Invalid Documents**: Validation for corrupted or invalid Word files

## Performance Considerations

- **Preview Truncation**: Long documents are truncated with "Show More" indicators
- **Lazy Loading**: Previews are loaded only when expanded
- **Caching**: Browser caching for preview content
- **Memory Management**: Temporary files are cleaned up appropriately

## Future Enhancements

- **Pagination**: Support for very long documents
- **Search**: Search within preview content
- **Print Support**: Direct printing from preview
- **Excel Preview**: Similar functionality for Excel files
- **PDF Preview**: Extension to PDF documents

## Troubleshooting

### Common Issues

1. **Preview Not Showing**
   - Check if mammoth library is installed
   - Verify the file is a valid .docx document
   - Check browser console for JavaScript errors

2. **Styling Issues**
   - Ensure CSS classes are properly applied
   - Check for conflicting styles in custom CSS

3. **Performance Issues**
   - Consider truncating very long documents
   - Check memory usage for large files

### Debug Information

Enable debug logging to see preview generation details:
```python
import logging
logging.getLogger('apps.agents.tools.word_preview').setLevel(logging.DEBUG)
```

## Testing

### Test Cases

1. **Basic Functionality**
   - Generate Word document with simple text
   - Verify preview appears and is readable

2. **Formatting Support**
   - Test headings, lists, tables, bold/italic text
   - Verify formatting is preserved in preview

3. **Error Handling**
   - Test with corrupted Word files
   - Test with missing mammoth library

4. **Security**
   - Test preview access with different user sessions
   - Verify HTML sanitization works correctly

### Manual Testing

1. Create a Word document through the chat interface
2. Verify the preview section appears
3. Test expand/collapse functionality
4. Test full window view
5. Verify download still works correctly