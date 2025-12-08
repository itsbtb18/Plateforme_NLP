# Chatbot Quick Start Guide

## ⚡ Quick Setup (5 Minutes)

### Step 1: Configure Environment
Add to your `.env` file (or create it in `Plateforme/` directory):
```bash
# FastAPI Configuration
FASTAPI_URL=http://localhost:8000
FASTAPI_API_KEY=your-api-key-here
```

### Step 2: Database is Ready
Migrations already applied! ✅

### Step 3: Start FastAPI Backend
Make sure your FastAPI server is running:
```bash
# Your FastAPI should be running on the URL specified in FASTAPI_URL
# Default: http://localhost:8000
```

### Step 4: Start Django Server
```bash
cd d:\PFE\Plateforme_NLP\Plateforme
python manage.py runserver
```

### Step 5: Access Chatbot
Open browser: **http://localhost:8000/chatbot/**

---

## 🎯 Usage Examples

### For Arabic NLP Research

#### Example 1: Research Question
**Mode**: Conversation  
**Question**: "ما هي أفضل الطرق لمعالجة اللغة العربية في التعلم العميق؟"

#### Example 2: Paper Analysis
**Mode**: Upload PDF  
1. Upload research paper PDF
2. Ask: "ما هي المنهجية المستخدمة في هذا البحث؟"

#### Example 3: Quick Definition
**Mode**: Quick Question  
**Question**: "Define tokenization in Arabic NLP"

#### Example 4: Detailed Discussion
**Mode**: Conversation  
1. "What are the challenges in Arabic NLP?"
2. "Can you explain morphological analysis?"
3. "How does this compare to English NLP?"

---

## 🔍 Admin Access

### View Chat History
**URL**: http://localhost:8000/admin/chatbot/

**Available Panels:**
- **Chat Sessions**: See all user conversations
- **Chat Messages**: Browse message history
- **Chat Feedback**: View user ratings

**Login**: Use your Django superuser account

---

## ⚙️ Configuration Options

### In `settings.py`:
```python
# Adjust these as needed:
CHATBOT_MAX_HISTORY = 20        # Conversation memory (default: 20 turns)
CHATBOT_MAX_TOKENS = 24000      # Max response length (default: 24k tokens)
CHATBOT_TIMEOUT = 120           # Request timeout (default: 120 seconds)
CHATBOT_MAX_FILE_SIZE = 10485760  # Max PDF size (default: 10MB)
```

### Rate Limiting:
In `chatbot/views.py` line 29:
```python
def check_rate_limit(user_id, limit=30, window=60):
    # Default: 30 requests per minute
    # Increase limit for power users: limit=60
```

---

## 🛠️ Troubleshooting

### "Unable to connect to the chatbot service"
**Fix**: Start FastAPI server and verify FASTAPI_URL in `.env`

### "Rate limit exceeded"
**Fix**: Wait 60 seconds or increase rate limit in views.py

### "Authentication required"
**Fix**: Make sure user is logged in to Django

### Messages not saving
**Fix**: Check database connection and run migrations:
```bash
python manage.py migrate chatbot
```

---

## 📊 What's New

### Major Improvements ✅
- ✅ **Database persistence**: All chats saved forever
- ✅ **Rate limiting**: Prevents abuse (30 req/min)
- ✅ **Admin interface**: Full chat management
- ✅ **Better errors**: User-friendly messages
- ✅ **Session tracking**: Never lose context
- ✅ **PDF tracking**: Know what's uploaded
- ✅ **Message history**: Complete audit trail
- ✅ **Arabic support**: Optimized for Arabic NLP

---

## 🚀 Key Features

### 1. Conversation Mode
- Multi-turn discussions
- Context memory
- Perfect for research questions

### 2. PDF Upload Mode
- Analyze papers & documents
- Up to 10MB files
- Ask questions about content

### 3. Quick Question Mode
- Fast standalone queries
- No context needed
- Great for definitions

### 4. Delete & Restart
- Clear conversation
- Start fresh
- Remove PDF context

---

## 💡 Pro Tips

### For Best Results:
1. **Be specific**: "Explain BERT for Arabic" vs "Tell me about NLP"
2. **Use conversation mode**: For follow-up questions
3. **Upload PDFs**: For paper-specific questions
4. **Check source field**: Verify where answers come from
5. **Rate responses**: Help improve the system

### Arabic NLP Research:
- Ask about: Morphology, syntax, semantics
- Topics: Tokenization, stemming, embeddings
- Papers: Upload and analyze research
- Comparisons: Arabic vs other languages

---

## 📝 Common Questions

**Q: How long is chat history kept?**  
A: Forever! All messages stored in database.

**Q: Can I share my chat?**  
A: Currently no, but you can export via admin panel.

**Q: What file types supported?**  
A: PDF only for now, up to 10MB.

**Q: How many questions can I ask?**  
A: 30 per minute per user.

**Q: Is my data private?**  
A: Yes, sessions are user-specific and isolated.

**Q: Can I delete my history?**  
A: Contact admin to delete specific sessions.

---

## 📞 Need Help?

1. **Check logs**: See Django console for errors
2. **Admin panel**: View session details at /admin/chatbot/
3. **README.md**: Full documentation in chatbot/README.md
4. **IMPROVEMENTS.md**: See what changed in chatbot/IMPROVEMENTS.md

---

## ✅ System Status

**Current Status**: ✅ **Ready for Production**

**What's Working:**
- ✅ Database models created
- ✅ Migrations applied
- ✅ Admin interface registered
- ✅ Rate limiting active
- ✅ Error handling improved
- ✅ Session management enhanced
- ✅ Message tracking enabled

**Configuration Required:**
- ⚠️ Set FASTAPI_URL in .env
- ⚠️ Set FASTAPI_API_KEY in .env
- ⚠️ Ensure FastAPI backend is running

---

**Last Updated**: November 25, 2025  
**Version**: 2.0 Professional Edition  
**Ready to use!** 🚀
