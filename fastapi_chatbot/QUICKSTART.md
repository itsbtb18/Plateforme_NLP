# 🚀 FastAPI Chatbot - Quick Start Guide

## ⚡ 5-Minute Setup

### Step 1: Install Dependencies (2 min)
```bash
cd d:\PFE\Plateforme_NLP\fastapi_chatbot
pip install -r requirements.txt
```

### Step 2: Configure Database (1 min)
```sql
-- Open PostgreSQL (pgAdmin or psql)
CREATE DATABASE nlp_platform;
\c nlp_platform
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 3: Update Database URL (30 sec)
Edit `.env` file and update this line:
```bash
DATABASE_URL=postgresql+asyncpg://YOUR_USER:YOUR_PASSWORD@localhost:5432/nlp_platform
```

Replace `YOUR_USER` and `YOUR_PASSWORD` with your PostgreSQL credentials.

### Step 4: Initialize & Load Data (1 min)
```bash
python setup.py
```

This will:
- ✅ Create all database tables
- ✅ Load platform documentation (5 docs)
- ✅ Load NLP knowledge base (6 entries)
- ✅ Load research resources (10 resources)

### Step 5: Start Service (30 sec)
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## ✅ Verify It's Working

### Test 1: Health Check
Open browser: http://localhost:8001/health

Expected response:
```json
{
  "status": "healthy",
  "service": "fastapi-chatbot",
  "version": "1.0.0"
}
```

### Test 2: API Documentation
Open browser: http://localhost:8001/docs

You'll see interactive Swagger UI with all endpoints.

### Test 3: Ask a Question
```bash
# Using PowerShell
$body = @{
    question = "What is Arabic stemming?"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8001/query" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"
```

Expected: Detailed answer about Arabic stemming!

## 🔗 Connect to Django

Update your Django `.env` file:
```bash
FASTAPI_URL=http://localhost:8001
```

Now Django chatbot will use this FastAPI service automatically!

## 🎯 What's Next?

### Test the Chatbot Features:

#### 1. Platform Questions
```
Question: "How do I create a project?"
Expected: Answer from platform documentation
```

#### 2. Arabic NLP Questions
```
Question: "ما هو التشكيل العربي؟"
Expected: Answer in Arabic about diacritization
```

#### 3. Resource Discovery
```
Question: "Show me Arabic NLP datasets"
Expected: List of relevant datasets with links
```

#### 4. PDF Analysis
```bash
1. Start conversation: POST /start_conversation
2. Upload PDF: POST /upload_pdf (with your research paper)
3. Ask questions: POST /ask with "What is the main contribution?"
```

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'app'"
**Solution:**
```bash
# Make sure you're in the fastapi_chatbot directory
cd d:\PFE\Plateforme_NLP\fastapi_chatbot
```

### Issue: "connection refused" to PostgreSQL
**Solution:**
1. Check PostgreSQL is running
2. Verify credentials in `.env`
3. Test connection: `psql -U postgres -d nlp_platform`

### Issue: "GROQ_API_KEY not found"
**Solution:** Already configured in `.env`! ✅

### Issue: Slow first request
**Normal!** First request loads embedding model (takes 10-20 seconds).
Subsequent requests are fast.

## 📊 Monitor Performance

```bash
# Watch logs
uvicorn app.main:app --reload --log-level debug

# Test response time
curl -w "\nTime: %{time_total}s\n" http://localhost:8001/health
```

## 🔥 Production Deployment

### Option 1: Local Production Mode
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

### Option 2: Docker
```bash
docker build -t fastapi-chatbot .
docker run -p 8001:8001 --env-file .env fastapi-chatbot
```

### Option 3: Systemd Service
Create `/etc/systemd/system/fastapi-chatbot.service`:
```ini
[Unit]
Description=FastAPI Chatbot Service
After=network.target postgresql.service

[Service]
User=your_user
WorkingDirectory=/path/to/fastapi_chatbot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable fastapi-chatbot
sudo systemctl start fastapi-chatbot
```

## 📈 Scaling Tips

### 1. Use Multiple Workers
```bash
uvicorn app.main:app --workers 4
```

### 2. Add Redis Caching
Install: `pip install redis aioredis`
Cache frequent queries and embeddings

### 3. Use GPU for Embeddings
Faster embedding generation with CUDA

### 4. Optimize pgvector
```sql
-- Create IVFFlat index for faster search
CREATE INDEX ON platform_docs USING ivfflat (embedding vector_cosine_ops);
```

## 🎓 Learning Resources

- **FastAPI Tutorial**: https://fastapi.tiangolo.com/tutorial/
- **pgvector Guide**: https://github.com/pgvector/pgvector
- **Groq API Docs**: https://console.groq.com/docs
- **RAG Patterns**: https://python.langchain.com/docs/use_cases/question_answering/

## ✨ Features Ready to Use

- ✅ **4 Question Types**: Platform, Knowledge, Resources, PDF
- ✅ **3 Languages**: Arabic, English, French
- ✅ **Vector Search**: Semantic similarity with pgvector
- ✅ **RAG Pipeline**: Retrieve + Generate answers
- ✅ **Session Management**: Track conversations
- ✅ **PDF Processing**: Extract and analyze papers
- ✅ **Multi-source**: Platform + Knowledge + Resources

## 🎉 You're Ready!

The FastAPI chatbot service is now running and ready to handle:
- Arabic NLP research questions
- Platform help and guidance
- Resource discovery
- PDF analysis

Start asking questions through the Django chatbot interface!

---

**Need Help?** Check the full README.md or logs for details.
