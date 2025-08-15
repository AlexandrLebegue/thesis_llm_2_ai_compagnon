# Multi-Conversation System Architecture

## Overview
The multi-conversation system will allow users to maintain multiple separate chat conversations within a single browser session. Each conversation will have its own documents, messages, and context.

## Data Model Changes

```mermaid
erDiagram
    Session ||--|| DocumentSession : has
    DocumentSession ||--o{ Conversation : contains
    Conversation ||--o{ Message : has
    Conversation ||--o{ Document : owns
    Conversation ||--|| DocumentContext : has
    Message ||--o{ Artifact : generates
    
    Conversation {
        uuid id
        string title
        datetime started_at
        datetime last_activity
        boolean is_active
    }
    
    Document {
        uuid id
        foreign_key conversation_id
        string original_name
        string file_path
        string status
    }
    
    DocumentContext {
        foreign_key conversation_id
        json context_data
        datetime last_updated
    }
```

## User Interface Flow

```mermaid
flowchart TD
    A[User Opens Chat] --> B[Load Session]
    B --> C{Has Conversations?}
    C -->|No| D[Create Default Conversation]
    C -->|Yes| E[Load Active Conversation]
    D --> F[Display Chat Interface]
    E --> F
    
    F --> G[Sidebar Shows Conversation List]
    G --> H[User Can Switch Conversations]
    G --> I[User Can Create New Conversation]
    G --> J[User Can Delete Conversation]
    
    H --> K[Load Selected Conversation]
    K --> L[Update Messages]
    K --> M[Update Documents]
    K --> N[Update Context]
    
    I --> O[Create New Conversation]
    O --> P[Switch to New Conversation]
    
    J --> Q{Last Conversation?}
    Q -->|No| R[Delete and Switch]
    Q -->|Yes| S[Prevent Deletion]
```

## Key Features

### 1. Conversation Management
- **Create**: Users can create new conversations with auto-generated or custom titles
- **Switch**: Click on any conversation in the sidebar to switch
- **Delete**: Remove conversations (except if it's the last one)
- **Rename**: Edit conversation titles inline

### 2. Document Isolation
- Each conversation maintains its own document collection
- Documents uploaded in one conversation are not visible in others
- Document count limits apply per conversation

### 3. Persistence
- Conversations are saved automatically
- Last active conversation is remembered and restored on page reload
- Message history is preserved per conversation

### 4. UI Components

#### Sidebar Enhancement
```
┌─────────────────────────┐
│ 📂 Documents            │
├─────────────────────────┤
│ [Upload Zone]           │
├─────────────────────────┤
│ 💬 Conversations        │
├─────────────────────────┤
│ [+ New Conversation]    │
├─────────────────────────┤
│ ▶ Sales Analysis       │
│   "Can you analyze..."  │
│   2 docs • 5 min ago    │
├─────────────────────────┤
│ ▶ Product Research     │
│   "Compare these..."    │
│   3 docs • 1 hour ago  │
├─────────────────────────┤
│ ▶ Meeting Notes        │
│   "Summarize the..."    │
│   1 doc • Yesterday    │
└─────────────────────────┘
```

## Implementation Phases

### Phase 1: Backend Model Changes
- Update models to support conversation relationships
- Create migrations
- Update DocumentContext to work per conversation

### Phase 2: API Endpoints
- Create/Delete/Rename conversations
- Switch active conversation
- List conversations for session

### Phase 3: Frontend Updates
- Add conversation list to sidebar
- Implement conversation switching
- Update document upload flow

### Phase 4: Testing & Polish
- Test multi-conversation workflows
- Add visual polish and animations
- Implement auto-cleanup for old conversations