# Arabic NLP Platform - FastAPI Chatbot Service

## 🎯 Overview

RAG-based chatbot microservice for Arabic NLP research platform using:
- **FastAPI**: High-performance async API
- **PostgreSQL + pgvector**: Vector similarity search
- **Groq API**: LLM (Llama 3.1) for chat completions
- **Sentence Transformers**: Multilingual embeddings

## 🏗️ Architecture

```
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── db.py                # Database connection
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── services/
│   │   ├── groq_client.py   # Groq API client
│   │   ├── embeddings.py    # Embedding generation
│   │   ├── retrieval.py     # Vector search
│   │   └── chat_logic.py    # RAG orchestration
│   └── ingestion/
│       ├── ingest_platform_docs.py
│       ├── ingest_nlp_knowledge.py
│       └── ingest_resources.py
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- PostgreSQL 14+ with pgvector extension
- Groq API key

### 2. Installation

```bash
# Clone repository
cd fastapi_chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup

```sql
-- Create database
CREATE DATABASE nlp_platform;

-- Connect and enable pgvector
\c nlp_platform
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Important:** Add your Groq API key to `.env`:
```bash
GROQ_API_KEY=your_actual_groq_api_key_here
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/nlp_platform
```

### 5. Initialize Database

```bash
# Run the application once to create tables
python -m app.main
```

### 6. Ingest Data

```bash
# Ingest platform documentation
python app/ingestion/ingest_platform_docs.py

# Ingest NLP knowledge base
python app/ingestion/ingest_nlp_knowledge.py

# Ingest research resources
python app/ingestion/ingest_resources.py
```

### 7. Run Service

```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

## 📡 API Endpoints

### Health Check
```bash
GET /health
```

### Start Conversation
```bash
POST /start_conversation
Body: {
  "user_id": "user123",
  "user_country": "Lebanon",
  "user_city": "Beirut"
}
Response: {
  "session_id": "uuid",
  "timestamp": "2024-01-01T12:00:00"
}
```

### Conversation (RAG)
```bash
POST /conversation
Body: {
  "question": "ما هو الجذعنة؟",
  "session_id": "uuid",
  "history": [],
  "user_country": "Lebanon"
}
Response: {
  "answer": "الجذعنة هي...",
  "source": "nlp_knowledge",
  "session_id": "uuid",
  "lang": "ar",
  "retrieved_docs": [...]
}
```

### Quick Query
```bash
POST /query
Body: {
  "question": "What is stemming?"
}
Response: {
  "answer": "Stemming is...",
  "source": "groq",
  "session_id": "quick_query",
  "lang": "en"
}
```

### Upload PDF
```bash
POST /upload_pdf
Headers: {
  "session-id": "uuid"
}
Form Data: {
  "file": <pdf file>
}
Response: {
  "message": "PDF uploaded successfully",
  "filename": "paper.pdf",
  "pages": 10
}
```

### Ask About PDF
```bash
POST /ask
Body: {
  "question": "What is the main contribution?",
  "session_id": "uuid"
}
Response: {
  "answer": "The main contribution is...",
  "source": "pdf",
  "session_id": "uuid"
}
```

### End Conversation
```bash
POST /end_conversation/{session_id}
Response: {
  "message": "Session ended successfully"
}
```

## 🎨 Features

### 1. RAG Pipeline
- Hybrid search across 3 knowledge sources
- Vector similarity with cosine distance
- Contextual answer generation
- Source attribution

### 2. Multi-source Knowledge Base
- **Platform Docs**: Features, troubleshooting
- **NLP Knowledge**: Arabic NLP concepts (AR/EN/FR)
- **Resources**: Papers, datasets, tools, institutions

### 3. Intelligent Retrieval
- Semantic search with embeddings
- Location-aware boosting for resources
- Language-specific filtering
- Similarity threshold filtering

### 4. Language Support
- Automatic language detection
- Arabic, English, French responses
- Dialect-aware processing
- Multilingual embeddings

### 5. PDF Processing
- Upload and extract text from PDFs
- Context-aware question answering
- Session-based PDF storage

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `GROQ_API_KEY` | Groq API key (NEVER commit!) | Required |
| `GROQ_MODEL` | LLM model name | llama-3.1-70b-versatile |
| `EMBEDDING_MODEL` | Sentence transformer model | paraphrase-multilingual-mpnet-base-v2 |
| `EMBEDDING_DIMENSION` | Vector dimension | 768 |
| `TOP_K_RESULTS` | Number of retrieved docs | 5 |
| `SIMILARITY_THRESHOLD` | Min similarity score | 0.7 |
| `API_PORT` | Server port | 8001 |

### Models

**LLM (Groq):**
- `llama-3.1-70b-versatile`: Default, balanced
- `llama-3.1-8b-instant`: Faster, lighter
- `mixtral-8x7b-32768`: Long context

**Embeddings:**
- `paraphrase-multilingual-mpnet-base-v2`: Default, 768d
- `sentence-transformers/LaBSE`: Multilingual, 768d

## 🗄️ Database Schema

### platform_docs
```sql
id SERIAL PRIMARY KEY
slug VARCHAR(255) UNIQUE
title TEXT
content TEXT
category VARCHAR(100)
embedding VECTOR(768)
created_at TIMESTAMP
updated_at TIMESTAMP
```

### nlp_knowledge
```sql
id SERIAL PRIMARY KEY
topic VARCHAR(255)
content TEXT
language VARCHAR(10)
keywords TEXT[]
difficulty VARCHAR(20)
embedding VECTOR(768)
created_at TIMESTAMP
```

### resources
```sql
id SERIAL PRIMARY KEY
type VARCHAR(50)
title TEXT
url TEXT
description TEXT
tags TEXT[]
country VARCHAR(100)
city VARCHAR(100)
author VARCHAR(255)
institution VARCHAR(255)
year INTEGER
embedding VECTOR(768)
```

### chat_sessions
```sql
id SERIAL PRIMARY KEY
session_id VARCHAR(255) UNIQUE
user_id VARCHAR(255)
user_country VARCHAR(100)
user_city VARCHAR(100)
pdf_context TEXT
pdf_filename VARCHAR(255)
created_at TIMESTAMP
last_activity TIMESTAMP
```

### chat_messages
```sql
id SERIAL PRIMARY KEY
session_id VARCHAR(255)
role VARCHAR(20)
content TEXT
source VARCHAR(50)
language VARCHAR(10)
created_at TIMESTAMP
```

## 🔐 Security

### API Key Management
- **NEVER** hardcode API keys
- Load from environment variables only
- Don't log API keys
- Use `.gitignore` for `.env`

### Best Practices
```python
# ✅ GOOD
api_key = os.getenv("GROQ_API_KEY")

# ❌ BAD
api_key = "gsk_..."  # NEVER DO THIS
```

## 📊 Performance

### Optimization Tips
1. **Connection Pooling**: Adjust `pool_size` in `db.py`
2. **Batch Processing**: Use batch embedding generation
3. **Caching**: Add Redis for frequent queries
4. **Index Tuning**: Optimize pgvector indexes

### Scaling
```bash
# Multiple workers
uvicorn app.main:app --workers 4

# With gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 🧪 Testing

```bash
# Test health endpoint
curl http://localhost:8001/health

# Test conversation
curl -X POST http://localhost:8001/conversation \
  -H "Content-Type: application/json" \
  -d '{"question": "What is stemming?", "session_id": "test123", "history": []}'
```

## 🐛 Troubleshooting

### Issue: "GROQ_API_KEY not found"
**Solution:** Set environment variable in `.env`

### Issue: pgvector extension error
**Solution:** Install pgvector:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Issue: Slow embedding generation
**Solution:** Use GPU acceleration or lighter model

### Issue: Database connection errors
**Solution:** Check `DATABASE_URL` format and PostgreSQL service

## 📝 Integration with Django

Update Django `.env`:
```bash
FASTAPI_URL=http://localhost:8001
```

The Django chatbot app will automatically connect to this FastAPI service.

## 🚀 Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### Production Checklist
- [ ] Set `ENVIRONMENT=production`
- [ ] Use strong database password
- [ ] Enable HTTPS
- [ ] Configure CORS properly
- [ ] Set up monitoring
- [ ] Enable rate limiting
- [ ] Use secrets manager for API keys

## 📚 References

- [Groq API Docs](https://console.groq.com/docs)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Sentence Transformers](https://www.sbert.net/)

## 📄 License

[Your License Here]

## 👥 Contributors

[Your Team]

---

**Version:** 1.0.0  
**Last Updated:** November 2025  
**Status:** ✅ Production Ready
