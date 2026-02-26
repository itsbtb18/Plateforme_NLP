# Project Chatroom Feature Documentation

## Overview

The **Project Chatroom** feature allows members of a project to have a private discussion space where they can:
- Send real-time messages
- Upload files and photos
- Discussed project-related topics securely

## Features

### 1. **Private Chatroom per Project**
- Each project automatically gets a dedicated chatroom upon creation
- Only accepted members of the project can access it
- The chatroom is automatically created when a project is created

### 2. **Real-time Messaging**
- WebSocket support for live messaging using Django Channels
- Typing indicators to show which members are typing
- Message timestamps and edit tracking

### 3. **File and Photo Uploads**
- Upload any type of file or photo to messages
- Automatic image detection (.jpg, .png, .gif, .webp, .bmp, .svg, .jpeg)
- File size tracking and metadata storage

### 4. **Access Control**
- Only project members with "accepted" status can access the chatroom
- Users can only edit/delete their own messages
- Project coordinators have additional admin privileges

## Database Models

### ProjectChat
- **Purpose**: Represents the chatroom for a project
- **Fields**:
  - `id` (UUID): Primary key
  - `project` (OneToOne): Reference to the project
  - `created_at`: Creation timestamp
  - `updated_at`: Last update timestamp

### ProjectChatMessage
- **Purpose**: Individual messages in the chatroom
- **Fields**:
  - `id` (UUID): Primary key
  - `chat` (ForeignKey): Reference to the projectchat
  - `author` (ForeignKey): The user who posted the message
  - `content` (TextField): Message content
  - `created_at`: Creation timestamp
  - `updated_at`: Last update timestamp
  - `is_edited` (Boolean): Whether the message was edited

### ProjectChatFileAttachment
- **Purpose**: Attached files and photos to messages
- **Fields**:
  - `id` (UUID): Primary key
  - `message` (ForeignKey): Reference to the message
  - `file` (FileField): The uploaded file
  - `attachment_type` (CharField): 'image' or 'file'
  - `original_filename` (CharField): Original file name
  - `file_size` (BigInt): File size in bytes
  - `uploaded_by` (ForeignKey): The user who uploaded
  - `uploaded_at`: Upload timestamp

## API Endpoints

### REST API (HTTP)

#### List Project Chats
```
GET /project-chat/chats/
```
Returns only chats for projects where the authenticated user is a member.

**Response:**
```json
{
  "count": 1,
  "results": [
    {
      "id": "uuid",
      "project": "project-uuid",
      "project_title": "Project Name",
      "last_message": { /* message object */ },
      "message_count": 5,
      "created_at": "2026-02-20T10:00:00Z",
      "updated_at": "2026-02-20T12:00:00Z"
    }
  ]
}
```

#### Get Chat Details
```
GET /project-chat/chats/{chat_id}/
```
Returns the full chat details including all messages.

**Response:**
```json
{
  "id": "uuid",
  "project": "project-uuid",
  "project_title": "Project Name",
  "messages": [
    {
      "id": "message-uuid",
      "author": { /* user object */ },
      "content": "Message text",
      "attachments": [ /* attachment objects */ ],
      "created_at": "2026-02-20T10:00:00Z",
      "updated_at": "2026-02-20T10:00:00Z",
      "is_edited": false
    }
  ],
  "created_at": "2026-02-20T10:00:00Z",
  "updated_at": "2026-02-20T10:00:00Z",
  "can_user_access": true
}
```

#### Send Message to Chat
```
POST /project-chat/chats/{chat_id}/send_message/
```
Send a text message to the chatroom.

**Request:**
```json
{
  "content": "Hello team, this is my message!"
}
```

**Response:**
```json
{
  "id": "message-uuid",
  "author": { /* user object */ },
  "content": "Hello team, this is my message!",
  "attachments": [],
  "created_at": "2026-02-20T10:05:00Z",
  "updated_at": "2026-02-20T10:05:00Z",
  "is_edited": false
}
```

#### Upload File to Message
```
POST /project-chat/chats/{chat_id}/upload_file/
```
Upload a file or photo to an existing message.

**Form Data:**
```
- message_id (required): UUID of the message to attach to
- file (required): The file to upload
```

**Response:**
```json
{
  "id": "attachment-uuid",
  "file": "/media/project_chat_attachments/2026/02/20/filename.pdf",
  "attachment_type": "file",
  "original_filename": "filename.pdf",
  "file_size": 1024000,
  "uploaded_by": { /* user object */ },
  "uploaded_at": "2026-02-20T10:10:00Z",
  "is_image": false,
  "file_extension": ".pdf"
}
```

#### Get Chat Messages
```
GET /project-chat/chats/{chat_id}/messages/
```
Get all messages in a specific chat.

#### Update Message
```
PUT /project-chat/messages/{message_id}/
PATCH /project-chat/messages/{message_id}/
```
Edit your own message.

#### Delete Message
```
DELETE /project-chat/messages/{message_id}/
```
Delete your own message (or admin can delete any message).

### WebSocket API (Real-time)

#### Connect to Chat
```
ws://localhost/ws/project-chat/{chat_id}/
```

#### Send Message (WebSocket)
```json
{
  "type": "chat_message",
  "content": "Hello team!"
}
```

#### Typing Indicator
```json
{
  "type": "typing",
  "is_typing": true
}
```

#### Receive Message
```json
{
  "type": "chat_message",
  "message": {
    "id": "message-uuid",
    "author": { /* user object */ },
    "content": "Message text",
    "created_at": "2026-02-20T10:00:00Z"
  }
}
```

#### Receive Typing Indicator
```json
{
  "type": "typing_indicator",
  "user_id": "user-uuid",
  "user_name": "John Doe",
  "is_typing": true
}
```

## Permission System

### Access Rules
- **Must be authenticated**: Anonymous users cannot access chats
- **Must be project member**: User must be in `ProjectMember` for the project
- **Must have 'accepted' status**: Only accepted members can view/post
- **Own message only**: Users can only edit/delete their own messages
- **Admin exception**: Staff users can delete any message

### Example Permission Check (in view):
```python
@require_http_methods(["GET"])
def can_user_access_chat(request, chat_id):
    chat = ProjectChat.objects.get(id=chat_id)
    can_access = chat.can_user_access(request.user)
    return JsonResponse({"can_access": can_access})
```

## Usage Example

### Python/Django Shell
```python
from project_chatroom.models import ProjectChat, ProjectChatMessage
from projects.models import Project
from django.contrib.auth import get_user_model

User = get_user_model()

# Get a project's chatroom
project = Project.objects.first()
chat = project.chatroom

# Get all members
members = chat.get_members()

# Check if user can access
user = User.objects.first()
can_access = chat.can_user_access(user)

# Create a message
message = ProjectChatMessage.objects.create(
    chat=chat,
    author=user,
    content="Hello team!"
)

# Get all messages
messages = chat.messages.all()
```

### JavaScript Frontend (WebSocket)
```javascript
// Connect to chat
const chatId = 'your-chat-uuid';
const socket = new WebSocket(`ws://localhost/ws/project-chat/${chatId}/`);

// Listen for messages
socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'chat_message') {
    console.log('New message:', data.message);
  } else if (data.type === 'typing_indicator') {
    console.log(`${data.user_name} is ${data.is_typing ? 'typing' : 'not typing'}`);
  }
};

// Send message
socket.send(JSON.stringify({
  type: 'chat_message',
  content: 'Hello team!'
}));

// Send typing indicator
socket.send(JSON.stringify({
  type: 'typing',
  is_typing: true
}));

// Close connection
socket.close();
```

## Admin Interface

All models are registered in Django Admin:
- Navigate to `Admin > Project Chat`
- View and manage:
  - **Project Chats**: See all project chatrooms and message counts
  - **Project Chat Messages**: View and delete messages
  - **File Attachments**: Monitor uploaded files

## Configuration

### Settings (in settings.py)
```python
# Already configured - no additional settings needed
# The app is registered in INSTALLED_APPS
```

### Media Files Storage
- Attachments are stored in: `MEDIA_ROOT/project_chat_attachments/YYYY/MM/DD/`
- File size limit depends on your Django file upload settings (default: 2.5MB)

## Error Handling

### Common Errors

**403 Forbidden - User Not a Project Member**
```json
{
  "detail": "You do not have permission to access this chat."
}
```

**400 Bad Request - Empty Message**
```json
{
  "detail": "Message content cannot be empty"
}
```

**404 Not Found - Message Not Found**
```json
{
  "detail": "Not found."
}
```

## Performance Considerations

- Messages are ordered by `created_at` ASC (oldest first)
- Use pagination for large chatrooms (HTTP API)
- WebSocket connections are stateful - implement reconnection logic
- Consider lazy-loading messages and using database indexes on `chat` and `created_at`

## Security

- ✅ Authentication required for all operations
- ✅ Project membership validated on every access
- ✅ Users can only modify their own messages
- ✅ File uploads are validated for type
- ✅ WebSocket connections validated with AuthMiddleware
- ⚠️ Consider implementing rate limiting for message/upload endpoints

## Future Enhancements

Potential features for future development:
- Message reactions/emojis
- Message threading/replies
- Search functionality
- Message pinning
- User read receipts
- Message encryption
- Integration with project tasks/milestones
- @mentions and notifications
- Message scheduling
- Draft messages

---

**Last Updated**: February 20, 2026
**Status**: Production Ready
