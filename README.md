# 🌐 Plateforme NLP - Arabic Natural Language Processing Research Platform

[![Django](https://img.shields.io/badge/Django-5.1.7-green.svg)](https://www.djangoproject.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-blue.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://www.postgresql.org/)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.11-yellow.svg)](https://www.elastic.co/)
[![License](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Platform](#running-the-platform)
- [Applications Overview](#applications-overview)
- [API Documentation](#api-documentation)
- [Development](#development)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

**Plateforme NLP** is a comprehensive web-based research platform dedicated to Arabic Natural Language Processing (NLP) and Artificial Intelligence research. It provides a collaborative environment for researchers, academics, and AI professionals across the Arab world to share knowledge, resources, and collaborate on projects.

The platform combines a Django-based web application with a FastAPI-powered AI chatbot service, offering both traditional web features and cutting-edge AI-assisted research capabilities.

### Vision
To create the leading Arabic NLP research hub, fostering collaboration and knowledge sharing among researchers, institutions, and AI professionals in the Arabic-speaking world.

### Target Audience
- NLP Researchers and Scientists
- University Professors and Students
- AI/ML Professionals
- Academic Institutions
- Research Organizations
- AI Enthusiasts in Arabic-speaking regions

## ✨ Key Features

### 🎓 Academic & Research Management
- **User Profiles**: Comprehensive profiles with specializations, institutions, and portfolios
- **Institutions Database**: Registry of universities and research centers
- **Research Projects**: Project management with collaboration tools
- **Scientific Resources**: Repository for papers, theses, articles, and memoirs
- **Courses & Materials**: Academic course sharing platform
- **Events Management**: Conferences, workshops, seminars, and calls for papers

### 🔬 NLP Tools & Resources
- **NLP Tools Repository**: Catalog of Arabic NLP tools (tokenization, stemming, NER, etc.)
- **Corpora Database**: Collection of Arabic text corpora
- **Documents Library**: Research papers, theses, and scientific articles
- **Multilingual Support**: Arabic, English interface with automatic language detection

### 💬 Collaboration & Communication
- **Real-time Forum**: WebSocket-based discussion rooms and topics
- **Q&A Platform**: Community-driven question and answer system
- **Social Posts**: Share updates, research findings, and discussions
- **Notifications System**: Real-time notifications for all activities
- **Private Messaging**: (Through notifications system)

### 🤖 AI-Powered Features
- **RAG-Based Chatbot**: Intelligent assistant for NLP research questions
- **PDF Analysis**: Upload and query research papers
- **Multilingual Chat**: Supports Arabic, English, French
- **Context-Aware Responses**: Retrieves information from platform knowledge base
- **Quick Queries**: Fast answers without maintaining conversation context

### 🔍 Advanced Search
- **Elasticsearch Integration**: Powerful full-text search across all resources
- **Multilingual Search**: Arabic and English search with stemming
- **Phonetic Search**: Find resources even with spelling variations
- **Faceted Filtering**: Filter by type, institution, field, language, etc.
- **Smart Ranking**: Relevance-based result ordering

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX (Port 80)                          │
│                     Reverse Proxy & Load Balancer                │
└───────────┬──────────────────────────────────────┬───────────────┘
            │                                      │
            │ /api/*                              │ /* (root)
            │                                      │
┌───────────▼──────────┐              ┌───────────▼──────────────┐
│   FastAPI Chatbot    │              │   Django Application     │
│     (Port 8001)      │              │      (Port 8888)        │
│                      │              │                          │
│ • RAG Pipeline       │              │ • Web Interface         │
│ • Groq LLM          │              │ • Business Logic        │
│ • Vector Search     │              │ • Django Channels       │
│ • PDF Processing    │              │ • WebSockets           │
└──────────┬───────────┘              └────────────┬─────────────┘
           │                                       │
           │                                       │
┌──────────▼───────────────────────────────────────▼─────────────┐
│                   PostgreSQL + pgvector                         │
│               Database (Port 5432)                              │
│                                                                 │
│ • User Data         • Resources        • Vector Embeddings    │
│ • Projects          • Events           • Chat History         │
│ • Forum Messages    • Q&A             • Sessions              │
└─────────────────────────────────────────────────────────────────┘
           │                                       │
┌──────────▼───────────┐              ┌───────────▼──────────────┐
│  Redis (Port 6379)   │              │ Elasticsearch (Port 9200)│
│                      │              │                          │
│ • Django Channels    │              │ • Full-text Search      │
│ • WebSocket Layer    │              │ • Resource Indexing     │
│ • Caching           │              │ • Multilingual Analysis │
└─────────────────────┘              └──────────────────────────┘
```

### Application Architecture

**Django Application (Plateforme)**
```
Django Project
├── accounts       → User management & authentication
├── institutions   → Universities & research centers
├── resources      → NLP tools, corpora, courses, documents
├── projects       → Research projects & collaboration
├── events         → Conferences, workshops, seminars
├── forum          → Real-time discussion platform
├── QA             → Question & Answer system
├── notifications  → Real-time notification service
├── search         → Elasticsearch integration
├── chatbot        → AI chatbot interface (Django side)
├── translate      → Translation utilities
└── pages          → Static pages & landing
```

**FastAPI Chatbot Service**
```
FastAPI Service
├── main.py           → API endpoints
├── config.py         → Configuration
├── db.py            → Database connection
├── models.py        → SQLAlchemy models
├── schemas.py       → Pydantic schemas
├── services/
│   ├── groq_client.py   → LLM integration
│   ├── embeddings.py    → Sentence transformers
│   ├── retrieval.py     → Vector search
│   └── chat_logic.py    → RAG orchestration
└── ingestion/
    ├── ingest_platform_docs.py
    ├── ingest_nlp_knowledge.py
    └── ingest_resources.py
```

## 🛠️ Technology Stack

### Backend
- **Django 5.1.7**: Web framework
- **FastAPI 0.115.0**: Async API framework for AI services
- **Daphne**: ASGI server for Django Channels
- **Django Channels**: WebSocket support
- **Uvicorn**: ASGI server for FastAPI

### Database & Storage
- **PostgreSQL 14+**: Main database
- **pgvector**: Vector similarity search
- **Redis 7**: Caching and Django Channels backend
- **Elasticsearch 8.11**: Full-text search engine

### AI & NLP
- **Groq API**: LLM (Llama 3.3-70B)
- **Sentence Transformers**: Multilingual embeddings
- **LangDetect**: Language detection
- **PyArabic**: Arabic text processing
- **PyPDF2**: PDF text extraction

### Frontend
- **HTML5/CSS3**: Modern web standards
- **JavaScript**: Client-side interactivity
- **Bootstrap 5**: UI framework (via crispy-forms)
- **HTMX**: Modern web interactions
- **WebSockets**: Real-time communication

### Infrastructure
- **Docker & Docker Compose**: Containerization
- **Nginx**: Reverse proxy and load balancer
- **Linux**: Production environment

### Development Tools
- **python-decouple**: Environment configuration
- **python-dotenv**: Environment variables
- **psycopg2**: PostgreSQL adapter
- **django-allauth**: Authentication & OAuth
- **django-elasticsearch-dsl**: Elasticsearch integration

## 📁 Project Structure

```
Plateforme_NLP/
├── docker-compose.yml          # Docker services orchestration
├── init-db.sql                 # Database initialization
├── README.md                   # This file
│
├── fastapi_chatbot/           # AI Chatbot Microservice
│   ├── app/
│   │   ├── main.py            # FastAPI application
│   │   ├── config.py          # Configuration
│   │   ├── db.py              # Database connection
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   └── ingestion/         # Data ingestion scripts
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── Plateforme/                # Django Application
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   │
│   ├── Plateforme/            # Django project settings
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── accounts/              # User management
│   │   ├── models.py          # CustomUser model
│   │   ├── views.py
│   │   ├── forms.py
│   │   ├── managers.py
│   │   └── middleware.py
│   │
│   ├── institutions/          # Universities & centers
│   │   ├── models.py
│   │   ├── views.py
│   │   └── forms.py
│   │
│   ├── resources/             # NLP resources
│   │   ├── models.py          # Course, NLPTool, Corpus, Document
│   │   ├── views.py
│   │   └── forms.py
│   │
│   ├── projects/              # Research projects
│   │   ├── models.py          # Project, ProjectMember
│   │   ├── views.py
│   │   └── forms.py
│   │
│   ├── events/                # Events & conferences
│   │   ├── models.py          # Event, EventRegistration
│   │   ├── views.py
│   │   └── forms.py
│   │
│   ├── forum/                 # Discussion forum
│   │   ├── models.py          # Topic, ChatRoom, Message
│   │   ├── consumers.py       # WebSocket consumers
│   │   ├── routing.py
│   │   └── views.py
│   │
│   ├── QA/                    # Q&A Platform
│   │   ├── models.py          # Question, Answer, Post, Comment
│   │   └── views.py
│   │
│   ├── notifications/         # Notification system
│   │   ├── models.py
│   │   ├── consumers.py       # WebSocket consumers
│   │   ├── services.py
│   │   └── views.py
│   │
│   ├── search/                # Search functionality
│   │   ├── documents.py       # Elasticsearch documents
│   │   └── views.py
│   │
│   ├── chatbot/               # Chatbot interface
│   │   ├── models.py          # ChatSession, ChatMessage
│   │   ├── views.py
│   │   └── README.md
│   │
│   ├── translate/             # Translation utilities
│   ├── pages/                 # Static pages
│   │
│   ├── templates/             # HTML templates
│   ├── static/                # Static files (CSS, JS, images)
│   ├── media/                 # User uploads
│   └── locale/                # Translation files
│       ├── ar/                # Arabic translations
│       └── en/                # English translations
│
└── nginx/                     # Nginx configuration
    ├── nginx.conf
    └── conf.d/
        └── default.conf
```

## 📦 Installation

### Prerequisites

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **Git**
- **Groq API Key** (for chatbot functionality)

### Quick Start with Docker (Recommended)

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/Plateforme_NLP.git
cd Plateforme_NLP
```

2. **Create environment file**
```bash
cp .env.example .env
```

3. **Configure environment variables**
Edit `.env` with your settings:
```bash
# Database
POSTGRES_DB=nlp_platform
POSTGRES_USER=nlp_admin
POSTGRES_PASSWORD=your_secure_password

# Redis
REDIS_PASSWORD=your_redis_password

# Django
DJANGO_SECRET_KEY=your_secret_key_here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Groq API (for chatbot)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# Elasticsearch
ELASTICSEARCH_HOST=http://elasticsearch:9200
```

4. **Build and start services**
```bash
docker-compose build
docker-compose up -d
```

5. **Run migrations**
```bash
docker-compose exec django python manage.py migrate
```

6. **Create superuser**
```bash
docker-compose exec django python manage.py createsuperuser
```

7. **Collect static files**
```bash
docker-compose exec django python manage.py collectstatic --noinput
```

8. **Compile translations**
```bash
docker-compose exec django python manage.py compilemessages --ignore=.venv
```

9. **Create Elasticsearch indices**
```bash
docker-compose exec django python manage.py search_index --create
docker-compose exec django python manage.py search_index --populate
```

10. **Ingest chatbot knowledge base** (optional)
```bash
docker-compose exec fastapi python app/ingestion/ingest_platform_docs.py
docker-compose exec fastapi python app/ingestion/ingest_nlp_knowledge.py
docker-compose exec fastapi python app/ingestion/ingest_resources.py
```

11. **Access the platform**
- **Main Platform**: http://localhost
- **Admin Panel**: http://localhost/admin
- **FastAPI Docs**: http://localhost/api/docs
- **FastAPI Health**: http://localhost/api/health

### Manual Installation (Development)

#### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3.9 python3-pip python3-venv postgresql postgresql-contrib redis-server
```

**macOS:**
```bash
brew install python@3.9 postgresql redis
```

#### 2. Setup PostgreSQL

```bash
# Start PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql   # macOS

# Create database and user
sudo -u postgres psql
```

```sql
CREATE DATABASE nlp_platform;
CREATE USER nlp_admin WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE nlp_platform TO nlp_admin;

-- Enable pgvector extension
\c nlp_platform
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

#### 3. Setup Redis

```bash
# Start Redis
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

#### 4. Setup Django Application

```bash
cd Plateforme

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Compile translations
python manage.py compilemessages

# Collect static files
python manage.py collectstatic

# Run development server
python manage.py runserver
```

#### 5. Setup FastAPI Chatbot

```bash
cd ../fastapi_chatbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your GROQ_API_KEY

# Initialize database
python -m app.main  # Run once to create tables

# Ingest knowledge base (optional)
python app/ingestion/ingest_platform_docs.py
python app/ingestion/ingest_nlp_knowledge.py

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

#### 6. Setup Elasticsearch (Optional)

```bash
# Using Docker
docker run -d \
  --name nlp_elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0

# Create and populate indices
cd Plateforme
source venv/bin/activate
python manage.py search_index --create
python manage.py search_index --populate
```

## ⚙️ Configuration

### Environment Variables

#### Django (.env in Plateforme/)
```bash
# Database
DATABASE_URL=postgresql://nlp_admin:password@localhost:5432/nlp_platform

# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis
REDIS_URL=redis://:redis_password@localhost:6379/0

# Elasticsearch
ELASTICSEARCH_HOST=http://localhost:9200

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
EMAIL_USE_TLS=True

# FastAPI Chatbot
FASTAPI_URL=http://localhost:8001
CHATBOT_MAX_HISTORY=20
CHATBOT_MAX_TOKENS=24000
CHATBOT_TIMEOUT=180
CHATBOT_MAX_FILE_SIZE=10485760
```

#### FastAPI (.env in fastapi_chatbot/)
```bash
# Database
DATABASE_URL=postgresql+asyncpg://nlp_admin:password@localhost:5432/nlp_platform

# Groq API
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Embeddings
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
EMBEDDING_DIMENSION=768

# API Settings
API_HOST=0.0.0.0
API_PORT=8001
ENVIRONMENT=development

# Elasticsearch
ELASTICSEARCH_HOST=http://localhost:9200

# RAG Configuration
TOP_K_RESULTS=5
SIMILARITY_THRESHOLD=0.7
```

### Django Settings Overview

Key settings in `Plateforme/settings.py`:

```python
# Installed Apps
INSTALLED_APPS = [
    'daphne',              # ASGI server
    'channels',            # WebSockets
    'django.contrib.admin',
    # ... Django core apps
    
    # Project apps
    'accounts', 'institutions', 'resources', 'projects',
    'events', 'forum', 'QA', 'notifications',
    'search', 'chatbot', 'translate', 'pages',
    
    # Third-party
    'allauth',             # Authentication
    'crispy_forms',        # Forms styling
    'widget_tweaks',       # Form widgets
]

# Custom User Model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Internationalization
LANGUAGE_CODE = 'en'
LANGUAGES = [
    ('en', 'English'),
    ('ar', 'Arabic'),
]

# Channels
ASGI_APPLICATION = 'Plateforme.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Elasticsearch
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': os.getenv('ELASTICSEARCH_HOST', 'http://localhost:9200'),
        'timeout': 120,
        'sniff_on_start': True,
    },
}
```

## 🚀 Running the Platform

### Using Docker Compose (Production-like)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose stop

# Restart specific service
docker-compose restart django

# View service status
docker-compose ps

# Execute command in container
docker-compose exec django python manage.py shell
```

### Manual Development Setup

**Terminal 1: Django**
```bash
cd Plateforme
source venv/bin/activate
python manage.py runserver 0.0.0.0:8888
```

**Terminal 2: FastAPI**
```bash
cd fastapi_chatbot
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Terminal 3: Redis**
```bash
redis-server
```

**Terminal 4: PostgreSQL**
```bash
sudo systemctl start postgresql
```

**Terminal 5: Elasticsearch** (optional)
```bash
docker run -p 9200:9200 -e "discovery.type=single-node" \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Platform** | http://localhost | Main web interface |
| **Admin** | http://localhost/admin | Django admin panel |
| **API Docs** | http://localhost/api/docs | FastAPI interactive docs |
| **API Health** | http://localhost/api/health | Health check endpoint |
| **Elasticsearch** | http://localhost:9200 | Search engine |
| **Redis** | localhost:6379 | Cache & channels |
| **PostgreSQL** | localhost:5432 | Database |

## 📚 Applications Overview

### 1. **Accounts** - User Management

**Models:**
- `CustomUser`: Extended user model with AI specializations, institution, bio, verification

**Features:**
- Email-based authentication (no username)
- Account verification with codes
- User profiles with specializations (ML, NLP, Computer Vision, etc.)
- Social links (LinkedIn, Twitter, Facebook)
- Avatar uploads
- Admin approval workflow

**Specializations:**
- Machine Learning
- Deep Learning
- Natural Language Processing
- Computer Vision
- Reinforcement Learning
- AI Ethics
- And 10+ more AI fields

### 2. **Institutions** - Academic Organizations

**Models:**
- `Institution`: Universities, research centers
- `Country`: Country database
- `Specialty`: Research specialties

**Features:**
- Institution registry
- Geolocation (country, city)
- Specializations
- Contact information
- Logo uploads

### 3. **Resources** - Research Materials

**Models:**
- `Course`: Academic courses
- `NLPTool`: NLP software tools
- `Corpus`: Text corpora
- `Document`: Base model for research documents
  - `Article`: Scientific articles with DOI
  - `Thesis`: PhD theses
  - `Memoir`: Master's theses

**Features:**
- Multilingual titles (Arabic/English)
- Keywords and tagging
- View counting
- Language detection
- File attachments
- Citation generation
- Elasticsearch indexing

**NLP Tool Types:**
- Tokenization
- Stemming
- Named Entity Recognition
- POS Tagging
- Sentiment Analysis
- Machine Translation

### 4. **Projects** - Research Collaboration

**Models:**
- `Project`: Research projects
- `ProjectMember`: Team members with roles

**Features:**
- Project status tracking (Ongoing, Completed, Planned)
- Coordinator assignment
- Member management with roles
- Join requests workflow
- Leave requests
- File attachments
- Date tracking

### 5. **Events** - Scientific Conferences

**Models:**
- `Event`: Conferences, workshops, seminars
- `EventRegistration`: User registrations

**Features:**
- Event types (Conference, Workshop, Seminar, Call for Papers, Hackathon)
- Domain tagging (NLP, Speech, AI, etc.)
- Virtual/Physical location
- Submission deadlines
- Registration tracking
- Approval workflow
- Calendar integration

**Event Status:**
- Upcoming
- Ongoing
- Past
- Days until deadline

### 6. **Forum** - Real-time Discussions

**Models:**
- `Topic`: Discussion topics
- `ChatRoom`: Real-time chat rooms
- `Message`: Chat messages
- `BannedUser`: Moderation

**Features:**
- WebSocket-based real-time chat
- Topic organization
- Message editing
- User banning
- Moderation tools
- Timestamps

**WebSocket Consumer:**
- Real-time message delivery
- User presence
- Typing indicators

### 7. **QA** - Question & Answer

**Models:**
- `Question`: User questions
- `Answer`: Community answers
- `Post`: Social posts
- `Comment`: Post comments with nested replies

**Features:**
- Q&A system
- Social timeline
- Post likes
- Nested comments
- Image/file uploads
- Slug-based URLs

### 8. **Notifications** - Real-time Alerts

**Models:**
- `Notification`: User notifications

**Features:**
- WebSocket-based real-time notifications
- Notification types
- Read/unread status
- Context processors for template integration
- Service layer for creating notifications

**WebSocket Consumer:**
- Real-time notification delivery
- Badge counters
- Auto-refresh

### 9. **Search** - Full-text Search

**Elasticsearch Documents:**
- `UserDocument`: User search
- `CourseDocument`: Course search
- `ToolDocument`: NLP tool search
- `CorpusDocument`: Corpus search
- `ResourceDocument`: Document search
- `ProjectDocument`: Project search
- `EventDocument`: Event search
- `InstitutionDocument`: Institution search

**Features:**
- Arabic/English analyzers
- Stemming and normalization
- Phonetic search
- Multi-field search
- Faceted filtering
- Highlighting

**Analyzers:**
- `arabic_analyzer`: Arabic stemming, normalization
- `english_analyzer`: English stemming
- `phonetic_analyzer`: Sound-alike matching

### 10. **Chatbot** - AI Assistant

**Django Models:**
- `ChatSession`: User chat sessions
- `ChatMessage`: Conversation history
- `ChatFeedback`: User ratings

**Features:**
- RAG-based conversations
- PDF upload and analysis
- Quick queries
- Session management
- Rate limiting (30 req/min)
- Multilingual (AR/EN/FR)
- Source tracking

**Modes:**
- Conversation: Context-aware chat
- PDF Analysis: Question papers
- Quick Query: Fast answers
- Delete & Restart: New session

### 11. **Translate** - Translation Utilities

**Features:**
- Translation helpers
- Language detection
- Multilingual content support

## 🔌 API Documentation

### Django REST Endpoints

*Note: Django primarily serves HTML views, not REST API. For API needs, use FastAPI service.*

**Key Views:**
- `/admin/`: Admin panel
- `/accounts/`: User management
- `/resources/`: Resource browsing
- `/projects/`: Project management
- `/events/`: Event listing
- `/forum/`: Forum interface
- `/qa/`: Q&A platform
- `/chatbot/`: Chatbot interface
- `/search/`: Search interface

### FastAPI Chatbot API

**Base URL:** `http://localhost/api/` (via Nginx) or `http://localhost:8001/`

#### Authentication
Optional API key via header:
```bash
Authorization: Bearer your-api-key
```

#### Endpoints

##### 1. Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "fastapi-chatbot",
  "version": "1.0.0"
}
```

##### 2. Start Conversation
```http
POST /start_conversation
Content-Type: application/json

{
  "user_id": "user123",
  "user_country": "Lebanon",
  "user_city": "Beirut"
}
```

**Response:**
```json
{
  "session_id": "uuid-here",
  "timestamp": "2025-02-05T12:00:00"
}
```

##### 3. Send Message (RAG)
```http
POST /conversation
Content-Type: application/json

{
  "question": "ما هو الجذعنة؟",
  "session_id": "uuid-here",
  "history": [
    {"role": "user", "content": "Previous question"},
    {"role": "assistant", "content": "Previous answer"}
  ],
  "user_country": "Lebanon"
}
```

**Response:**
```json
{
  "answer": "الجذعنة هي عملية...",
  "source": "nlp_knowledge",
  "session_id": "uuid-here",
  "lang": "ar",
  "retrieved_docs": [
    {
      "content": "...",
      "similarity": 0.85,
      "metadata": {}
    }
  ]
}
```

##### 4. Quick Query
```http
POST /query
Content-Type: application/json

{
  "question": "What is stemming?"
}
```

**Response:**
```json
{
  "answer": "Stemming is the process...",
  "source": "groq",
  "session_id": "quick_query",
  "lang": "en"
}
```

##### 5. Upload PDF
```http
POST /upload_pdf
Headers:
  session-id: uuid-here
  Content-Type: multipart/form-data

Form Data:
  file: <pdf file>
```

**Response:**
```json
{
  "message": "PDF uploaded successfully",
  "filename": "paper.pdf",
  "pages": 10,
  "session_id": "uuid-here"
}
```

##### 6. Ask About PDF
```http
POST /ask
Content-Type: application/json

{
  "question": "What is the main contribution?",
  "session_id": "uuid-here"
}
```

**Response:**
```json
{
  "answer": "The main contribution is...",
  "source": "pdf",
  "session_id": "uuid-here",
  "lang": "en"
}
```

##### 7. End Session
```http
POST /end_conversation/{session_id}
```

**Response:**
```json
{
  "message": "Session ended successfully",
  "session_id": "uuid-here"
}
```

#### Error Responses

```json
{
  "detail": "Error message"
}
```

**Status Codes:**
- `200`: Success
- `400`: Bad request
- `404`: Not found
- `500`: Internal server error

## 🧪 Development

### Running Tests

```bash
# Django tests
cd Plateforme
python manage.py test

# Specific app
python manage.py test accounts

# With coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
```

### Code Quality

```bash
# Linting
pip install flake8
flake8 .

# Type checking
pip install mypy
mypy .

# Code formatting
pip install black
black .
```

### Database Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations

# Rollback
python manage.py migrate app_name 0001_previous_migration
```

### Elasticsearch Management

```bash
# Create indices
python manage.py search_index --create

# Rebuild indices
python manage.py search_index --rebuild

# Populate indices
python manage.py search_index --populate

# Delete indices
python manage.py search_index --delete
```

### Creating Sample Data

```python
# Django shell
python manage.py shell

# Create sample user
from accounts.models import CustomUser
user = CustomUser.objects.create_user(
    email='test@example.com',
    password='password123',
    full_name='Test User',
    speciality='nlp'
)

# Create sample institution
from institutions.models import Institution
inst = Institution.objects.create(
    name='Test University',
    acronym='TU',
    city='Beirut',
    country='Lebanon'
)
```

### Translation Management

```bash
# Create message files
python manage.py makemessages -l ar
python manage.py makemessages -l en

# Compile translations
python manage.py compilemessages --ignore=.venv
```

## 🚢 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use strong `SECRET_KEY`
- [ ] Setup HTTPS/SSL
- [ ] Configure email backend
- [ ] Setup database backups
- [ ] Configure persistent volumes
- [ ] Enable Redis persistence
- [ ] Setup monitoring (Sentry, etc.)
- [ ] Configure log aggregation
- [ ] Setup CDN for static files
- [ ] Enable rate limiting
- [ ] Configure firewalls
- [ ] Setup domain and DNS
- [ ] Configure CORS properly
- [ ] Use secrets manager for API keys

### Docker Production Deployment

1. **Update docker-compose.yml for production**

```yaml
services:
  django:
    build:
      context: ./Plateforme
      dockerfile: Dockerfile.prod  # Create production Dockerfile
    environment:
      DEBUG: "False"
      # Use secrets for sensitive data
    restart: always
    # ... other production settings
```

2. **Use Docker secrets**

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt
  django_secret:
    file: ./secrets/django_secret.txt
```

3. **Deploy**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Cloud Deployment Options

#### AWS
- **EC2**: Run Docker Compose on EC2 instances
- **ECS**: Container orchestration with Fargate
- **RDS**: Managed PostgreSQL
- **ElastiCache**: Managed Redis
- **S3**: Static and media files
- **CloudFront**: CDN

#### Azure
- **App Service**: Deploy Django and FastAPI
- **Container Instances**: Run Docker containers
- **Database for PostgreSQL**: Managed database
- **Cache for Redis**: Managed Redis
- **Blob Storage**: Static/media files

#### Google Cloud
- **Cloud Run**: Serverless containers
- **Cloud SQL**: Managed PostgreSQL
- **Memorystore**: Managed Redis
- **Cloud Storage**: Static/media files
- **Cloud CDN**: Content delivery

### Nginx SSL Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/your-cert.crt;
    ssl_certificate_key /etc/ssl/private/your-key.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # ... rest of configuration
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Write docstrings for functions and classes
- Add type hints where appropriate
- Keep functions small and focused

### Commit Messages

Follow conventional commits:
```
feat: Add new feature
fix: Fix bug
docs: Update documentation
style: Format code
refactor: Refactor code
test: Add tests
chore: Update dependencies
```

### Pull Request Process

1. Update README.md with details of changes
2. Update documentation
3. Add tests for new features
4. Ensure all tests pass
5. Update requirements.txt if dependencies changed
6. Get approval from maintainers

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- **Project Lead**: [Your Name]
- **Backend Development**: [Team Members]
- **Frontend Development**: [Team Members]
- **AI/ML**: [Team Members]
- **DevOps**: [Team Members]

## 📞 Support

- **Documentation**: [docs.your-domain.com](https://docs.your-domain.com)
- **Issues**: [GitHub Issues](https://github.com/yourusername/Plateforme_NLP/issues)
- **Email**: support@your-domain.com
- **Discord**: [Join our community](https://discord.gg/your-invite)

## 🙏 Acknowledgments

- Arabic NLP research community
- Open source contributors
- Universities and research institutions
- Groq for LLM API
- All contributors and supporters

## 📊 Project Stats

- **Lines of Code**: 50,000+
- **Django Apps**: 12
- **Models**: 40+
- **API Endpoints**: 10+
- **Supported Languages**: Arabic, English
- **Database Tables**: 45+

## 🗺️ Roadmap

### Version 2.0 (Q2 2026)
- [ ] Mobile applications (iOS/Android)
- [ ] Advanced AI features
- [ ] Video streaming for lectures
- [ ] Live translation
- [ ] API rate limiting
- [ ] GraphQL API

### Version 2.5 (Q3 2026)
- [ ] Machine learning model repository
- [ ] Jupyter notebook integration
- [ ] Collaborative code editing
- [ ] Research analytics dashboard

### Version 3.0 (Q4 2026)
- [ ] Multi-tenancy support
- [ ] White-label solution
- [ ] Advanced reporting
- [ ] Custom workflows

---

**Built with ❤️ for the Arabic NLP Research Community**

*Last Updated: February 2026*
