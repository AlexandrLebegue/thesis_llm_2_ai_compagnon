# Authentication System Architecture

## Overview
The authentication system will provide three ways for users to access the Ultra PDF Chatbot 3000:
1. **Social Authentication** - Login with Google or GitHub
2. **Email/Password Authentication** - Traditional registration and login
3. **Guest Mode** - Continue without authentication (session-based data only)

## Authentication Flow Diagram

```mermaid
flowchart TB
    Start[User visits app] --> Modal[Authentication Modal Popup]
    Modal --> Choice{User Choice}
    
    Choice -->|Social Login| Social[Select Provider]
    Social --> Google[Google OAuth]
    Social --> GitHub[GitHub OAuth]
    Google --> OAuth[OAuth Flow]
    GitHub --> OAuth
    OAuth --> CreateUser[Create/Login User]
    
    Choice -->|Email/Password| EmailAuth[Login/Register Form]
    EmailAuth --> Login[Login with Credentials]
    EmailAuth --> Register[Register New Account]
    Login --> CreateUser
    Register --> CreateUser
    
    Choice -->|Guest Mode| Guest[Continue as Guest]
    Guest --> SessionUser[Session-based User]
    
    CreateUser --> AuthUser[Authenticated User]
    AuthUser --> PersistentData[Access Persistent Data]
    SessionUser --> SessionData[Access Session Data Only]
    
    PersistentData --> App[Main Application]
    SessionData --> App
```

## Data Model Changes

```mermaid
erDiagram
    User ||--o{ Conversation : owns
    User ||--o{ Document : owns
    User ||--o{ Artifact : owns
    User {
        int id PK
        string email
        string username
        string first_name
        string last_name
        boolean is_guest
        datetime date_joined
    }
    
    Conversation {
        int id PK
        int user_id FK
        int session_id FK
        string title
        boolean is_active
        datetime created_at
        datetime last_activity
    }
    
    Document {
        int id PK
        int user_id FK
        int conversation_id FK
        string file_path
        string file_name
        datetime uploaded_at
    }
    
    Message {
        int id PK
        int conversation_id FK
        string content
        string role
        datetime created_at
    }
    
    Artifact {
        int id PK
        int user_id FK
        int message_id FK
        string file_path
        string artifact_type
        datetime created_at
    }
```

## Key Components

### 1. Authentication Modal
- Appears on first visit
- Built with Alpine.js for interactivity
- HTMX for seamless form submissions
- Three clear options: Social login, Email/Password, Guest mode

### 2. Django-Allauth Integration
- Handles social authentication providers
- Manages email verification
- Provides account management views

### 3. User Model Extension
- Custom User model extending AbstractUser
- `is_guest` field to distinguish guest users
- Links to all user-generated content

### 4. Middleware Layer
- Checks authentication status
- Redirects unauthenticated users to login modal
- Manages guest session conversion to authenticated user

### 5. Data Migration Strategy
- Preserve existing session-based data
- Allow guests to claim their data when registering
- Link orphaned data to new user accounts

## Security Considerations

1. **OAuth Security**
   - Secure storage of client secrets in environment variables
   - HTTPS required for production OAuth callbacks
   - CSRF protection on all forms

2. **Session Management**
   - Secure session cookies
   - Session expiry for guest users
   - Remember me functionality for authenticated users

3. **Data Privacy**
   - Guest data cleaned up after session expiry
   - User data encryption at rest
   - GDPR compliance for user data deletion

## User Experience Flow

1. **First Visit**
   - Modal appears with authentication options
   - Clear explanation of benefits for each option
   - Easy guest mode access

2. **Guest to User Conversion**
   - Prompt to save work when guest performs significant actions
   - Easy upgrade path from guest to registered user
   - Data preservation during conversion

3. **Returning Users**
   - Automatic login if "Remember me" was selected
   - Quick access to previous conversations and documents
   - Profile management in sidebar

## Technology Stack

- **Backend**: Django + Django-Allauth
- **Frontend**: Alpine.js + HTMX + Tailwind CSS
- **Authentication**: OAuth 2.0 (Google, GitHub) + Django Auth
- **Database**: SQLite (development) / PostgreSQL (production)