# Conversation History Feature

## Overview

The conversation history feature enables the chatbot to maintain context across multiple messages in a conversation. This allows for more coherent and contextual responses by providing the LLM with recent conversation history.

## Implementation Details

### Configuration

The feature is configured in `chatbot/settings/base.py`:

```python
# Conversation History Settings
MAX_CONVERSATION_HISTORY = 10  # Number of previous messages to include in LLM context
```

### Architecture

The conversation history is implemented across several components:

#### 1. ChatbotOrchestrator (`apps/agents/orchestrator.py`)

- **`_get_conversation_history(conversation_id)`**: Fetches the last N messages from the database
- **`_build_prompt(instruction, context, conversation_id)`**: Builds LLM prompts with conversation history
- **`process_request(..., conversation_id)`**: Updated to accept conversation ID parameter

#### 2. Chat Views (`apps/chat/views.py`)

- **Synchronous processing**: Passes `conversation_id` to orchestrator
- **Asynchronous processing**: Passes `conversation_id` to Celery task

#### 3. Agent Tasks (`tasks/agent_tasks.py`)

- **`run_agent_task_async(..., conversation_id)`**: Updated to accept and pass conversation ID

### Message Flow

```
User Message → Chat View → Orchestrator → LLM
                    ↓
            conversation_id passed
                    ↓
        Fetch last 10 messages
                    ↓
         Format with role markers
                    ↓
         Include in LLM prompt
```

### Prompt Structure

The LLM receives prompts in this format:

```
=== Conversation History ===
User: Can you analyze the Excel file?
Assistant: I've analyzed the Excel file. It contains sales data...
User: What's the total revenue?
Assistant: The total revenue is $45,230...

=== Available Documents ===
- sales_data.xlsx (Excel): Contains Q1 2024 sales information...

=== Current Request ===
User request: Create a chart showing monthly trends
```

## Features

### 1. Conversation Context
- Includes last 10 messages by default
- Preserves chronological order (oldest to newest)
- Excludes system messages for clarity

### 2. Role Formatting
- Clear role markers: "User:" and "Assistant:"
- Content truncation for very long messages (>500 chars)

### 3. Error Handling
- Graceful handling of missing conversations
- Logging of fetch errors
- Fallback to empty history on errors

### 4. Performance Optimization
- Database query optimization with ordering and limiting
- Message content truncation to prevent excessive token usage

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_CONVERSATION_HISTORY` | 10 | Number of previous messages to include |

## Database Impact

- Queries the `Message` model for recent conversation history
- Uses efficient ordering and limiting
- Excludes system messages from history

## Future Enhancements

Potential improvements for future versions:

1. **Token Management**: Add smart token counting to prevent context overflow
2. **Message Summarization**: Summarize older messages when approaching token limits
3. **Selective History**: Include only relevant messages based on content similarity
4. **Conversation Branching**: Support for multiple conversation threads

## Usage Examples

### Basic Conversation Flow

```
User: "What's in the uploaded Excel file?"
Assistant: "The Excel file contains sales data with columns for date, product, and revenue..."

User: "What's the total revenue?"
Assistant: "Based on our previous analysis of the Excel file, the total revenue is $45,230."
```

The second response includes context from the first exchange, allowing the assistant to reference "our previous analysis."

### Document Context Persistence

```
User: "Analyze the quarterly report"
Assistant: "I've analyzed the quarterly report. Key findings include..."

User: "Create a chart from that data"
Assistant: "I'll create a chart using the quarterly report data we just analyzed..."
```

The assistant maintains awareness of the previously analyzed document.

## Testing

To test the conversation history feature:

1. Start a new conversation
2. Upload a document and ask for analysis
3. Ask follow-up questions that reference the previous analysis
4. Verify that the assistant maintains context and doesn't ask for re-clarification

## Troubleshooting

### Common Issues

1. **No conversation history**: Check that `conversation_id` is being passed correctly
2. **Database errors**: Verify Message model relationships are intact
3. **Performance issues**: Consider reducing `MAX_CONVERSATION_HISTORY` value

### Logging

Conversation history fetching is logged at DEBUG level:
```
WARNING: Error fetching conversation history: [error message]
```

## Security Considerations

- Conversation history is limited to the current session
- No cross-session data leakage
- Message content is truncated to prevent excessive memory usage
- Error handling prevents information disclosure