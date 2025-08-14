# SmolAgents Tools Troubleshooting Guide

This guide helps resolve common issues with the SmolAgents tools after the robustness improvements.

## Table of Contents

1. [Tool Output Parsing Errors](#tool-output-parsing-errors)
2. [JSON Input Issues](#json-input-issues)
3. [Excel Generation Problems](#excel-generation-problems)
4. [Chart Generation Errors](#chart-generation-errors)
5. [File Creation Issues](#file-creation-issues)
6. [Word Document Problems](#word-document-problems)
7. [Performance Issues](#performance-issues)
8. [Debugging Tips](#debugging-tips)

---

## Tool Output Parsing Errors

### Problem: "Key tool_name_key='name' not found in the generated tool call"

**Symptoms:**
- Error messages about tool parsing failures
- "Got keys: ['type', 'title', 'data'] instead" errors
- SmolAgents framework misinterpreting tool outputs as tool definitions

**Root Cause:**
The SmolAgents framework can sometimes mistake tool output dictionaries for tool definition metadata when they contain certain keys like 'type', 'title', 'data', 'name', etc.

**Solutions:**

1. **Automatic Fix (Already Implemented):**
   - All tools now automatically sanitize their outputs to prevent this issue
   - Output dictionaries with suspicious keys are wrapped in safe containers
   - No action needed from users - this is handled automatically

2. **If errors persist:**
   - Check logs for "Sanitized potentially confusing output" messages
   - Restart the application to ensure all fixes are loaded
   - Try rephrasing requests to use simpler language

3. **Manual workaround (if needed):**
   ```python
   # If calling tools directly, you can extract clean output:
   from apps.agents.tools.tool_utils import ToolOutputSanitizer
   clean_output = ToolOutputSanitizer.extract_actual_output(tool_result)
   ```

**Prevention:**
- This issue is now automatically prevented by output sanitization
- Tools wrap potentially confusing outputs in safe containers
- Framework error handling catches and manages parsing failures gracefully

---

## JSON Input Issues

### Problem: "Invalid JSON data specification" errors

**Symptoms:**
- Tools reject JSON input with quote-related errors
- Mixed quote formats causing parsing failures
- Python-style dictionaries not being accepted

**Solutions:**

1. **Use consistent quote formats:**
   ```python
   # ✅ Good - Double quotes for JSON
   '{"type": "bar", "data": {"x": ["A", "B"], "y": [1, 2]}}'
   
   # ✅ Also works - Single quotes (automatically converted)
   "{'type': 'bar', 'data': {'x': ['A', 'B'], 'y': [1, 2]}}"
   
   # ❌ Avoid - Mixed quotes without proper escaping
   '{"type": 'bar', "data": {"x": ["A", "B"], "y": [1, 2]}}'
   ```

2. **Check for common JSON errors:**
   - Trailing commas: `{"key": "value",}` → `{"key": "value"}`
   - Single quotes around keys: `{'key': 'value'}` → `{"key": "value"}`
   - Missing quotes: `{key: value}` → `{"key": "value"}`

3. **Use the validation examples:**
   If you get a validation error, the tool will provide a working example. Copy and modify it.

### Problem: "Validation error" messages

**Symptoms:**
- Input structure doesn't match expected schema
- Missing required fields
- Wrong data types

**Solutions:**

1. **Check required fields for each tool:**

   **Excel Generator:**
   ```json
   {
     "sheets": [
       {
         "name": "SheetName",
         "tables": [
           {
             "data": [
               ["Header1", "Header2"],
               ["Value1", "Value2"]
             ]
           }
         ]
       }
     ]
   }
   ```

   **Chart Generator:**
   ```json
   {
     "type": "bar",
     "data": {
       "x": ["Label1", "Label2"],
       "y": [10, 20]
     }
   }
   ```

2. **Use the schema examples provided in error messages**

---

## Excel Generation Problems

### Problem: Excel files created but appear empty

**Symptoms:**
- File exists but shows "may be empty" warning
- Sheets are created but contain no data
- File size is very small (< 10KB)

**Solutions:**

1. **Check data structure format:**
   ```python
   # ✅ Correct format
   data_structure = {
       "sheets": [{
           "name": "Sales",
           "tables": [{
               "data": [
                   ["Product", "Sales"],  # Headers
                   ["Widget A", 100],     # Data row 1
                   ["Widget B", 150]      # Data row 2
               ]
           }]
       }]
   }
   ```

2. **Verify data is not empty:**
   ```python
   # ❌ Empty data
   "data": []
   
   # ✅ Minimum viable data
   "data": [["Header"], ["Value"]]
   ```

3. **Check for data type issues:**
   - Ensure nested lists are properly formatted
   - Avoid mixing data types in unexpected ways
   - Use strings for headers, appropriate types for data

### Problem: "DataFrame creation failed" errors

**Symptoms:**
- Pandas DataFrame errors in logs
- Data conversion failures
- Inconsistent row lengths

**Solutions:**

1. **Ensure consistent row lengths:**
   ```python
   # ❌ Inconsistent lengths
   [
       ["Name", "Age", "City"],
       ["John", 25],  # Missing city
       ["Jane", 30, "NYC", "Extra"]  # Too many fields
   ]
   
   # ✅ Consistent lengths
   [
       ["Name", "Age", "City"],
       ["John", 25, "Unknown"],
       ["Jane", 30, "NYC"]
   ]
   ```

2. **Handle None/null values:**
   ```python
   # Replace None with empty strings or appropriate defaults
   data = [["A", "B"], ["value", None]]  # Will be converted to ["value", ""]
   ```

---

## Chart Generation Errors

### Problem: "Chart file was not created" or empty chart files

**Symptoms:**
- Chart generation reports success but no file exists
- Chart file exists but is 0 bytes
- Matplotlib errors in logs

**Solutions:**

1. **Verify data format for chart type:**

   **Bar/Line/Scatter charts:**
   ```json
   {
     "type": "bar",
     "data": {
       "x": ["A", "B", "C"],
       "y": [10, 20, 15]
     }
   }
   ```

   **Pie charts:**
   ```json
   {
     "type": "pie", 
     "data": {
       "labels": ["Slice A", "Slice B"],
       "values": [30, 70]
     }
   }
   ```

2. **Check for data validation errors:**
   - Ensure `x` and `y` arrays have same length
   - Use numeric values for `y` and `values`
   - Provide meaningful labels

3. **Handle special characters in labels:**
   ```python
   # ✅ Safe labels
   "x": ["Product A", "Product B"]
   
   # ⚠️ May cause issues
   "x": ["Product/Service", "Product&More"]
   ```

### Problem: Chart data type mismatches

**Symptoms:**
- "requires x and y data arrays" errors
- Wrong chart type for data format

**Solutions:**

1. **Match data format to chart type:**
   - Bar/Line/Scatter: Use `x` and `y` arrays
   - Pie: Use `labels` and `values` arrays

2. **Convert data types if needed:**
   ```python
   # Ensure numeric data
   "y": [int(x) for x in string_numbers]
   ```

---

## File Creation Issues

### Problem: "Permission denied" or "File not found" errors

**Symptoms:**
- Cannot write to specified paths
- Access denied errors
- Files created in wrong location

**Solutions:**

1. **Use relative paths within project:**
   ```python
   # ✅ Good - relative to project
   "temp/my_file.xlsx"
   
   # ❌ Avoid - absolute paths may fail
   "C:/Users/username/documents/file.xlsx"
   ```

2. **Check disk space and permissions:**
   - Ensure temp directory is writable
   - Verify sufficient disk space

3. **Use appropriate file extensions:**
   - Excel: `.xlsx`
   - Word: `.docx`
   - Charts: `.png`, `.jpg`, `.svg`

### Problem: Files created with wrong content or corrupted

**Symptoms:**
- Files exist but cannot be opened
- Content doesn't match input
- Encoding issues

**Solutions:**

1. **Check file verification results:**
   - Tools now verify file creation and content
   - Look for verification warnings in responses

2. **Handle encoding issues:**
   ```python
   # For text content with special characters
   content = "Special chars: áéíóú"  # Should work automatically
   ```

---

## Word Document Problems

### Problem: Markdown formatting not working

**Symptoms:**
- Bold/italic text not formatted
- Headers appear as plain text
- Code blocks not monospaced

**Solutions:**

1. **Use correct markdown syntax:**
   ```markdown
   # Header 1
   ## Header 2
   
   **Bold text**
   *Italic text*
   
   - List item 1
   - List item 2
   
   ```
   Code block
   ```
   
   Inline `code`
   ```

2. **Escape special characters if needed:**
   ```markdown
   # This is a header
   \# This is not a header (escaped)
   ```

### Problem: Document appears empty or malformed

**Symptoms:**
- Document exists but shows no content
- Formatting completely broken
- Cannot open in Word

**Solutions:**

1. **Provide meaningful content:**
   ```python
   # ✅ Good
   content = "# Report\n\nThis is the introduction."
   
   # ❌ Empty content
   content = ""
   ```

2. **Check for title/content balance:**
   - Provide either title or content (or both)
   - Don't leave both empty

---

## Performance Issues

### Problem: Slow file generation or timeouts

**Symptoms:**
- Tools take very long to respond
- Large files cause memory issues
- Timeout errors

**Solutions:**

1. **Limit data size for large datasets:**
   ```python
   # For very large datasets, consider chunking
   if len(data) > 10000:
       # Process in chunks or warn user
   ```

2. **Optimize data structures:**
   - Use appropriate data types
   - Avoid deeply nested structures
   - Pre-process data when possible

3. **Monitor memory usage:**
   - Check logs for memory warnings
   - Consider streaming for very large files

---

## Debugging Tips

### Enable Debug Logging

1. **Check application logs:**
   ```bash
   tail -f logs/chatbot.log
   ```

2. **Look for debug messages:**
   - Tool start/end logging
   - JSON parsing details
   - File operation results
   - Validation outcomes

### Common Log Messages

**Success indicators:**
- `[tool_name] Starting tool execution`
- `[tool_name] JSON parsing - Result type: dict`
- `[tool_name] Input validation PASSED`
- `[tool_name] File creation SUCCESS`

**Warning indicators:**
- `JSON parsing failed, trying fallback`
- `Input validation FAILED`
- `File created but appears to have no data`

**Error indicators:**
- `All JSON parsing strategies failed`
- `File was not created`
- `Validation error`

### Testing Tools Independently

Use the test script to verify tool functionality:

```bash
python test_robust_tools.py
```

This will run comprehensive tests on all tools and identify specific issues.

### Manual Testing Examples

**Test Excel Generation:**
```python
from apps.agents.tools.excel_generator import ExcelGeneratorTool
tool = ExcelGeneratorTool()
result = tool.forward(
    '{"sheets": [{"name": "Test", "tables": [{"data": [["A"], ["1"]]}]}]}',
    "debug_test"
)
print(result)
```

**Test Chart Generation:**
```python
from apps.agents.tools.generate_chart_tool import GenerateChartTool
tool = GenerateChartTool()
result = tool.forward(
    '{"type": "bar", "data": {"x": ["A"], "y": [1]}}'
)
print(result)
```

---

## Getting Help

If you continue to experience issues:

1. **Check the logs first** - Most issues are logged with helpful details
2. **Run the test suite** - `python test_robust_tools.py`
3. **Review input format** - Compare with working examples in this guide
4. **Check file permissions** - Ensure temp directories are writable
5. **Verify dependencies** - Ensure all required packages are installed

## Common Error Codes

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| "Invalid JSON data specification" | Malformed JSON | Use provided examples |
| "Validation error" | Wrong data structure | Check required fields |
| "File was not created" | Permission/path issues | Use relative paths |
| "Chart file is empty" | Data format mismatch | Verify chart data format |
| "No valid data found" | Empty data arrays | Provide non-empty data |

Remember: The tools are now much more robust and will provide helpful error messages with examples when things go wrong!