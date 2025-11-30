# Chatbot Application - Professional Arabic NLP Research Assistant

## Overview
A professional AI-powered chatbot optimized for Arabic NLP research questions, integrated with FastAPI backend for advanced language processing capabilities.

## Features

### Core Capabilities
- ✅ **Conversation Mode**: Contextual multi-turn conversations with memory
- ✅ **PDF Analysis**: Upload and analyze research papers, documents (up to 10MB)
- ✅ **Quick Questions**: Fast standalone queries without context
- ✅ **Session Management**: Persistent sessions with database tracking
- ✅ **Rate Limiting**: 30 requests/minute per user to prevent abuse
- ✅ **Message History**: Full chat history stored in database
- ✅ **Multi-language**: Support for Arabic and English with automatic detection
- ✅ **Modern UI**: Professional gradient design with smooth animations

### Research-Specific Features
- Arabic NLP terminology support
- Technical accuracy for research questions
- Source tracking for bot responses
- PDF context awareness for paper analysis
- Configurable token limits for long-form answers

## Architecture

### Components
1. **Django Frontend**: User interface and session management
2. **FastAPI Backend**: AI processing and NLP operations
3. **PostgreSQL Database**: Chat history, sessions, and feedback
4. **Cloudinary**: Media storage for uploaded files

### Database Models

#### ChatSession
```python
- id: UUID (Primary Key)
- user: Foreign Key to User
- fastapi_session_id: Unique session identifier
- created_at, updated_at: Timestamps
- is_active: Session status
- pdf_uploaded, pdf_filename: PDF context tracking
```

#### ChatMessage
```python
- id: UUID (Primary Key)
- session: Foreign Key to ChatSession
- message_type: user | bot | system | error
- content: Message text
- timestamp: Message time
- source: Response source (bot, retrieval, etc.)
- language: Detected language (ar, en)
```

#### ChatFeedback
```python
- id: UUID (Primary Key)
- message: Foreign Key to ChatMessage
- user: Foreign Key to User
- rating: 1-5 stars
- comment: Optional feedback text
- created_at: Feedback timestamp
```

## Configuration

### Required Settings (`settings.py`)
```python
# FastAPI Backend
FASTAPI_URL = 'http://localhost:8000'  # Your FastAPI server URL
FASTAPI_API_KEY = 'your-api-key-here'  # Optional authentication

# Chatbot Configuration
CHATBOT_MAX_HISTORY = 20            # Conversation turns to remember
CHATBOT_MAX_TOKENS = 24000          # Max tokens per response
CHATBOT_TIMEOUT = 120               # Request timeout (seconds)
CHATBOT_MAX_FILE_SIZE = 10485760    # Max PDF size (10MB)
```

### Environment Variables (`.env`)
```bash
# FastAPI Configuration
FASTAPI_URL=http://localhost:8000
FASTAPI_API_KEY=your-secure-api-key-here

# Database (already configured)
DATABASE_URL=your-database-url
```

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Migrations
```bash
python manage.py makemigrations chatbot
python manage.py migrate
```

### 3. Configure FastAPI
Update `settings.py` or `.env` with your FastAPI server URL and API key.

### 4. Start FastAPI Backend
Your FastAPI server should expose these endpoints:
- `POST /start_conversation` - Initialize new session
- `POST /conversation` - Handle conversation mode
- `POST /ask` - Handle PDF-based questions
- `POST /query` - Handle quick questions
- `POST /upload_pdf` - Upload PDF files
- `POST /end_conversation/{session_id}` - End session

### 5. Run Django Server
```bash
python manage.py runserver
```

## Usage

### Accessing the Chatbot
Navigate to: `http://localhost:8000/chatbot/`

### Modes

#### 1. Conversation Mode (Default)
- Maintains context across multiple questions
- Best for: Research discussions, follow-up questions
- Session persists until explicitly deleted

#### 2. PDF Upload Mode
- Upload research papers or documents
- Ask questions about uploaded content
- Context: PDF content + conversation history
- Supports: PDF files up to 10MB

#### 3. Quick Question Mode
- Fast, standalone questions
- No conversation context
- Best for: Single-shot queries, definitions

#### 4. Delete & Restart
- Clears current session
- Starts fresh conversation
- Removes PDF context

## API Endpoints

### Django Views

#### `GET /chatbot/`
Render chatbot interface
- **Authentication**: Required
- **Returns**: HTML template with session_id

#### `POST /chatbot/ask/`
Handle all chatbot interactions
- **Authentication**: Required
- **Rate Limit**: 30 requests/minute
- **Body**:
  ```json
  {
    "mode": "conversation|upload|quick|delete",
    "question": "Your question here",
    "session_id": "session-uuid"
  }
  ```
- **Returns**:
  ```json
  {
    "answer": "Bot response",
    "source": "bot|retrieval|system",
    "lang": "ar|en",
    "session_id": "session-uuid"
  }
  ```

#### `POST /chatbot/start_new_session/`
Create new chat session
- **Authentication**: Required
- **Returns**:
  ```json
  {
    "session_id": "new-session-uuid",
    "timestamp": "2025-01-01T12:00:00"
  }
  ```

## Admin Interface

### Accessing Admin
Navigate to: `http://localhost:8000/admin/`

### Available Admin Panels

#### Chat Sessions
- View all user sessions
- Filter by: Active status, PDF uploads, date
- Search: User email, session ID, PDF filename
- Actions: View messages, deactivate sessions

#### Chat Messages
- View all messages across sessions
- Filter by: Message type, source, language, date
- Search: Content, session ID, user email
- Display: Message preview with full content on detail page

#### Chat Feedback
- View user ratings and comments
- Filter by: Rating, date
- Search: User email, comment text
- Display: Star ratings with color coding

## Rate Limiting

### Default Configuration
- **Limit**: 30 requests per minute per user
- **Window**: 60 seconds
- **Backend**: Django cache (configurable)

### Customization
Edit in `chatbot/views.py`:
```python
def check_rate_limit(user_id, limit=30, window=60):
    # Adjust limit and window as needed
```

## Error Handling

### Client-Side
- Network errors: Automatic retry suggestion
- Timeout errors: Clear user message
- Validation errors: Inline field validation

### Server-Side
- **401**: Authentication required
- **429**: Rate limit exceeded
- **400**: Invalid request format
- **503**: FastAPI service unavailable
- **504**: Request timeout
- **500**: Internal server error

All errors logged with context for debugging.

## Performance Optimization

### Database
- Indexed fields: `user`, `fastapi_session_id`, `timestamp`
- Optimized queries with `select_related` and `prefetch_related`

### Caching
- Rate limit data: Redis/Django cache
- Session data: Database with active indexes

### Frontend
- Lazy loading for message history
- Debounced input handling
- Optimized re-renders

## Security

### Authentication
- Required for all chatbot operations
- User-specific session isolation

### Rate Limiting
- Prevents abuse and DoS attacks
- Per-user tracking

### File Uploads
- Size validation: 10MB max
- Type validation: PDF only
- Secure filename handling

### API Security
- Optional API key authentication
- HTTPS recommended for production
- CSRF protection on all POST requests

## Maintenance

### Database Cleanup
Periodically clean old sessions:
```python
# In Django shell or management command
from chatbot.models import ChatSession
from datetime import timedelta
from django.utils import timezone

# Delete inactive sessions older than 90 days
old_date = timezone.now() - timedelta(days=90)
ChatSession.objects.filter(
    is_active=False,
    updated_at__lt=old_date
).delete()
```

### Monitoring
Check logs for:
- FastAPI connection errors
- Rate limit violations
- Failed message saves
- User feedback patterns

## Troubleshooting

### Common Issues

#### "Unable to connect to the chatbot service"
- **Cause**: FastAPI backend not running
- **Solution**: Start FastAPI server and verify FASTAPI_URL

#### "Request timeout"
- **Cause**: Long processing time
- **Solution**: Increase CHATBOT_TIMEOUT in settings

#### "Rate limit exceeded"
- **Cause**: Too many requests
- **Solution**: Wait 60 seconds or increase rate limit

#### Session not persisting
- **Cause**: Database connection issue
- **Solution**: Check database configuration and migrations

## Development

### Running Tests
```bash
python manage.py test chatbot
```

### Adding New Features
1. Update models if needed: `chatbot/models.py`
2. Add/modify views: `chatbot/views.py`
3. Update templates: `templates/chatbot/chatbot.html`
4. Run migrations: `python manage.py makemigrations && python manage.py migrate`
5. Test thoroughly

### Code Style
- Follow PEP 8 for Python
- Use Django best practices
- Document complex logic
- Add type hints where helpful

## Arabic NLP Research Features

### Optimized For
- ✅ NLP terminology (Arabic & English)
- ✅ Research paper analysis
- ✅ Technical explanations
- ✅ Multi-turn research discussions
- ✅ Citation and source tracking

### Best Practices
1. **Use PDF mode** for analyzing research papers
2. **Use conversation mode** for in-depth discussions
3. **Use quick mode** for definitions and fast lookups
4. Provide **specific questions** for better responses
5. Check **source field** to verify response origin

## Support

### Logging
All operations logged with level:
- **DEBUG**: Detailed operation logs
- **INFO**: Session creation, PDF uploads
- **WARNING**: Rate limits, missing sessions
- **ERROR**: API failures, database errors

### Getting Help
1. Check logs: `CHATBOT_*` settings
2. Verify FastAPI connectivity
3. Review admin panel for session details
4. Check rate limit status

## License
[Your License Here]

## Contributors
[Your Team/Name Here]

---

**Last Updated**: January 2025
**Version**: 2.0 (Professional Research Edition)
