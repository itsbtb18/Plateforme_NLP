# 📚 Rapport Détaillé — Chatbot Intelligent Multilingue (Sanad)

## Table des matières
1. [Vue d'ensemble](#vue-densemble)
2. [Architecture générale](#architecture-générale)
3. [Outils et technologies utilisés](#outils-et-technologies-utilisés)
4. [Fonctionnement détaillé](#fonctionnement-détaillé)
5. [Endpoints API](#endpoints-api)
6. [Modèles de données](#modèles-de-données)
7. [Services protagonistes](#services-protagonistes)
8. [Pipeline RAG complet](#pipeline-rag-complet)
9. [Configuration et déploiement](#configuration-et-déploiement)
10. [Améliorations futures](#améliorations-futures)

---

## Vue d'ensemble

Le **Chatbot Intelligent Multilingue** est un service FastAPI décentralisé qui fournit des capacités conversationnelles avancées à la plateforme Sanad. Il ne se limite pas à une simple question-réponse, mais implémente un **système RAG (Retrieval-Augmented Generation)** complet capable de :

- 🗣️ **Conversations contextualisées** avec gestion d'historique
- 📖 **Recherche hybride** (textuelle + sémantique)
- 📄 **Traitement de documents** (PDF, images, documents structurés)
- 🌐 **Intégration web** pour enrichissement des réponses
- 🔍 **Recherche institutionnelle** sur contenu interne
- 🏛️ **Requêtes juridiques** spécialisées
- 🤖 **Classification d'intentions** automatique
- ✅ **Vérification de fidélité** des réponses
- 🌍 **Support multilingue** (Arabe, Français, Anglais)

---

## Architecture générale

```
┌─────────────────────────────────────────────────────────────┐
│                  Client (Django Web)                         │
│        (Plateforme/chatbot/views.py & websockets)          │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP + WebSocket
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Chatbot Service (Port 8000)            │
│                     (app/main.py)                            │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  API Controllers (Conversation, Document, Search)      │ │
│ └──────────────┬──────────────────────────────────────────┘ │
│                │                                             │
│ ┌──────────────▼──────────────────────────────────────────┐ │
│ │           Service Layer (Orchestration)                 │ │
│ │  - Chat Logic (Intent → Routing → Response)            │ │
│ │  - Memory Service (Session Management)                 │ │
│ │  - Document Service (OCR, Chunking, Indexing)         │ │
│ │  - Platform Query Service (Content Search)             │ │
│ │  - Retrieval Service (Hybrid Search)                   │ │
│ └──────────────┬──────────────────────────────────────────┘ │
│                │                                             │
│ ┌──────────────▼──────────────────────────────────────────┐ │
│ │         Infrastructure Layer (Storage & AI)             │ │
│ │  - LLM Service (Groq API - Llama 3.3 70B)             │ │
│ │  - Embedding Service (BGE-M3 1024-dim)                │ │
│ │  - Vector DB (Qdrant - 6333, 6334)                    │ │
│ │  - Full-text Search (Elasticsearch 9200)              │ │
│ │  - Relational DB (PostgreSQL + SQLAlchemy)            │ │
│ │  - Cache Layer (Redis)                                 │ │
│ └──────────────┬──────────────────────────────────────────┘ │
└─────────────────┼──────────────────────────────────────────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
   [Qdrant]  [Elasticsearch] [PostgreSQL]
                              [Redis]
```

---

## Outils et technologies utilisés

### 1. **Framework Web**
- **FastAPI 0.100+** : Framework web asynchrone ultra-rapide
  - Support WebSocket natif
  - Auto-génération de documentation OpenAPI/Swagger
  - Validation de données automatique avec Pydantic
  - Gestion d'erreurs simplifiée

### 2. **Modèles de Langage (LLM)**
- **Groq API** : Accès cloud à des LLMs haute performance
  - **Llama 3.3 70B Versatile** : Modèle principal pour génération de réponses (user-facing)
    - 128K tokens de contexte
    - Performance ultra-rapide (~100 tokens/s)
    - Support multilingue natif
  - **Llama 3.1 8B Instant** : Modèle interne pour tâches légères
    - Classification d'intentions
    - Réécriture de requêtes
    - Classification de fidélité
    - Classification multilingue

### 3. **Embeddings et Vectorisation**
- **Sentence-Transformers** : Conversion texte→vecteurs
  - Modèle : **BAAI/bge-m3** (1024 dimensions)
    - Score MTEB : 68.5 (état de l'art)
    - Support bilingue arabe/français/anglais
    - Modèle dense et efficace
  - Vitesse : ~5000 textes/s sur GPU
  - Cache mémoire pour réutilisation

### 4. **Bases de données vectorielles**
- **Qdrant** (Port 6333 HTTP, 6334 gRPC)
  - Stockage natif de vecteurs haute dimension
  - Collections séparées par type de contenu
  - Filtrage hybride (métadonnées + similarité)
  - ANN (Approximate Nearest Neighbor) pour recherche rapide
  - Payload riche : IDs, sources, titres, dates
  - 5 collections gérées :
    1. `platform_resources` : Documents utilisateur
    2. `legal_knowledge` : Base juridique institutionnelle
    3. `research_papers` : Articles scientifiques
    4. `faq_general` : Questions fréquentes
    5. `web_cache` : Résultats de recherche web cachés

### 5. **Recherche Full-Text**
- **Elasticsearch** (Port 9200)
  - Indexation BM25 pour recherche par mots-clés
  - Plugins ICU et phonétique pour arabe/français
  - Analyseurs multilingues configurés
  - Recherche facettée sur métadonnées
  - Agrégations pour statistiques
  - Hybridation avec Qdrant via RRF (Reciprocal Rank Fusion)

### 6. **Base de données relationnelle**
- **PostgreSQL** + **SQLAlchemy**
  - Stockage des sessions de chat
  - Historique des messages
  - Métadonnées des documents utilisateur
  - Feedback utilisateur
  - Transactions ACID pour intégrité
  - Extension pgvector pour stockage d'embeddings optionnels

### 7. **Cache distribué**
- **Redis**
  - Session storage (sérialisation JSON)
  - Cache des embeddings fréquents
  - Rate-limiting par utilisateur
  - Queue Celery pour tâches asynchrones
  - TTL automatique sur données temporaires

### 8. **Traitement de documents**
- **PyMuPDF (fitz)** : Extraction de texte depuis PDFs
- **PyTesseract + Tesseract-OCR** : Reconnaissance optique de caractères
  - Support arabe, français, anglais
  - Détektion automatique de langue
- **Pillow (PIL)** : Traitement d'images
- **python-docx** : Extraction depuis documents Word
- **LibreOffice (en arrière-plan via CLI)** : Conversion de documents complexes

### 9. **Classification et NER**
- **spaCy** : Pipeline NLP léger
  - Tokenization multilingue
  - Lemmatization arabe/français
  - POS tagging
- **Transformers (HuggingFace)** : Modèles spécialisés
  - Classification d'intentions custom
  - Named Entity Recognition (NER)

### 10. **Recherche Web (optionnel)**
- **Exa AI** : Recherche web structurée (RAG fallback)
  - Résultats formatés pour processus RAG
  - Cache 24h pour limiter les appels
  - Max 10 appels/session, 30/heure
- **Tavily Search** : Recherche web user-triggered
  - Résultats de qualité pour recherche web standard
  - Inclus dans le contexte de réponse

### 11. **Orchestration asynchrone**
- **Celery** : Exécution de tâches longues
  - Indexation de documents en arrière-plan
  - Extraction OCR asynchrone
  - Génération d'embeddings batch
  - File d'attente Redis
- **asyncio** : Concurrence native en Python
  - Requêtes parallèles
  - I/O non-bloquant

### 12. **Sérialisation et validation**
- **Pydantic V2** : Modèles de données avec validation
  - Sérialisation JSON automatique
  - Conversion de type stricte
  - Documentation automatique des schémas
- **SQLAlchemy ORM** : Mapping objet-relationnel
  - Relations automatiques
  - Lazy loading avec async

---

## Fonctionnement détaillé

### 📊 Flux général d'une requête

```
User Query
    │
    ▼
┌─────────────────────────────────────────┐
│ 1. Classification d'intention           │
│    (Groq Llama 3.1 8B)                 │
│    → conversation?                      │
│    → quick_query?                       │
│    → platform_search?                   │
│    → legal_research?                    │
│    → web_search?                        │
└──────────┬──────────────────────────────┘
           │
    ┌──────┴──────────────────────────────────┐
    │                                         │
    ▼ conversation                    ▼ search_type
┌─────────────────────────────┐  ┌─────────────────────┐
│ 2a. Conversation Mode       │  │ 2x. Search Mode     │
│    - Load session history   │  │    - Platform only? │
│    - Retrieve context       │  │    - Legal docs?    │
│    - Last N messages        │  │    - Web search?    │
│    - Long context memory    │  └────────┬────────────┘
└──────────┬──────────────────┘           │
           │                              │
           ▼                              ▼
    ┌──────────────────────────────────────────────┐
    │ 3. Unified Retrieval (Hybrid Search)        │
    │                                              │
    │  a) Vector Search (Qdrant)                  │
    │     - Query embedding (BGE-M3)              │
    │     - Top-K similarity (k=5)                │
    │     - Threshold filtering (0.65)            │
    │                                              │
    │  b) Full-Text Search (Elasticsearch)        │
    │     - BM25 scoring                          │
    │     - Keyword matching                      │
    │     - Top-K results                         │
    │                                              │
    │  c) Fusion (RRF — Reciprocal Rank Fusion)  │
    │     - Combine scores vector + full-text    │
    │     - De-duplicate results                  │
    │     - Top-K final (k=5)                     │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │ 4. Context Assembly                          │
    │    - Retrieved chunks                        │
    │    - Document metadata                       │
    │    - Original source links                   │
    │    - Relevance scores                        │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │ 5. RAG Prompt Construction                   │
    │                                              │
    │ System: "You are an Arabic NLP expert..."  │
    │                                              │
    │ Retrieved Context:                           │
    │ "[1] Source: X, Score: 0.92                 │
    │      ...content chunk...                     │
    │  [2] Source: Y, Score: 0.85                 │
    │      ...content chunk..."                    │
    │                                              │
    │ Chat History (if conversation):             │
    │ User: "Previous question"                    │
    │ Bot: "Previous answer"                       │
    │ ...                                          │
    │                                              │
    │ User: "Current question"                     │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │ 6. Generation (Streaming)                    │
    │    Groq API - Llama 3.3 70B                 │
    │                                              │
    │    Max tokens: 2048                          │
    │    Temperature: 0.7                          │
    │    Top-p: 0.9                                │
    │                                              │
    │    Returns: token stream (Server-Sent Events)│
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │ 7. Faithfulness Verification                 │
    │    (Groq Llama 3.1 8B Internal)             │
    │                                              │
    │    Input:                                    │
    │    - Context retrieved                       │
    │    - Generated response                      │
    │    - Original query                          │
    │                                              │
    │    Classification binaire : Faithful/Unfaithful│
    │    (post-processing)                         │
    └──────────────┬───────────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────────┐
    │ 8. Response & Storage                        │
    │    - Save to PostgreSQL (ChatMessage)        │
    │    - Link to ChatSession                     │
    │    - Store metadata (timestamp, source, etc) │
    │    - Update user conversation list           │
    │    - Send to client (JSON)                   │
    └──────────────────────────────────────────────┘
```

### 🔄 Cycle de vie d'une session de chat

```
┌────────────────────────────────────────────────────────┐
│ New Session (User clicks "New Chat")                  │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────┐
    │ Django → FastAPI                   │
    │ POST /sessions/create              │
    │ {user_id, optional: context_type}  │
    └────────────┬───────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────┐
    │ FastAPI Service Memory Service     │
    │ - Generate UUID session_id         │
    │ - Create in Flask memory (Redis)   │
    │ - Initialize history buffer        │
    │ - Store in PostgreSQL (ChatSession)│
    │ - Return session_id to client      │
    └────────────┬───────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
    User types        Context specified
    message           (document/project/content)
        │                 │
        └────────┬────────┘
                 │
                 ▼
    ┌────────────────────────────────────┐
    │ Django → FastAPI                   │
    │ POST /conversation                 │
    │ {session_id, user_query, context}  │
    └────────────┬───────────────────────┘
                 │
                 ▼
    ┌────────────────────────────────────┐
    │ Chat Logic Service                 │
    │ 1. Load session from Redis         │
    │ 2. Add user message to history     │
    │ 3. Classify intent                 │
    │ 4. Route to appropriate handler    │
    │ 5. Generate response (streaming)   │
    │ 6. Update session history          │
    │ 7. Save ChatMessage in DB          │
    └────────────┬───────────────────────┘
                 │
    ┌────────────┴──────────────────┐
    │ Session persists in Redis     │
    │ (until expiry or user logout) │
    │                               │
    │ Max history size: 20 messages │
    │ Automatic summarization if    │
    │ exceeds 12 messages           │
    └───────────────────────────────┘
```

### 📄 Pipeline de traitement de documents

```
User uploads PDF/Image
        │
        ▼
┌──────────────────────────────────────┐
│ 1. Validation & Storage              │
│    - Max 20 MB par fichier           │
│    - Check content-type              │
│    - Generate unique file ID         │
│    - Save to disk + DB metadata      │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 2. Extraction de texte               │
│    a) If PDF:                        │
│       - PyMuPDF fast extraction      │
│       - Preserve layout/tables       │
│                                       │
│    b) If scanned/image:              │
│       - Tesseract OCR               │
│       - Detect language (en/fr/ar)  │
│                                       │
│    c) If Word/RTF:                   │
│       - python-docx parsing          │
│       - Preserve formatting          │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 3. Nettoyage & Normalisation         │
│    - Remove extra whitespace         │
│    - Normalize Unicode (NFD)         │
│    - Detect language per section     │
│    - Remove boilerplate              │
│    - Paragraph detection             │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 4. Chunking                          │
│    - Chunk size: 512 tokens          │
│    - Overlap: 64 tokens              │
│    - Preserve sentence boundaries    │
│    - Max 500 chunks/document         │
│    - Calculate token count           │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 5. Embedding & Vectorization         │
│    - BGE-M3 encoding                 │
│    - Batch processing (GPU if avail) │
│    - 1024-dim dense vectors          │
│    - Cache frequent embeddings       │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 6. Indexing (Parallèle)              │
│                                       │
│  a) Vector Index (Qdrant)            │
│     - Store vectors + metadata       │
│     - Collection: user_documents     │
│     - Payload: chunk_id, source_id   │
│        filename, page, score         │
│                                       │
│  b) Full-text Index (Elasticsearch) │
│     - Index text content             │
│     - Keyword analysis               │
│     - Doc metadata fields            │
│                                       │
│  c) BM25 Index (In-memory)          │
│     - Rank documents by relevance    │
│     - Quick keyword refresh          │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ 7. Status & Notification             │
│    - Update document status (Ready)  │
│    - Store in PostgreSQL             │
│    - Notify user (chat message)      │
│    - Index complete, searchable      │
└──────────────────────────────────────┘
```

---

## Endpoints API

### 🗂️ Session Management

#### `POST /sessions/create`
**Création d'une nouvelle session de chat**
```json
Request:
{
  "context_type": "project",           // optional
  "context_id": "550e8400-e29b-41d4"   // optional
}

Response:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-04-11T10:30:00Z"
}
```

#### `GET /sessions`
**Lister toutes les sessions de l'utilisateur**
```json
Response:
{
  "sessions": [
    {
      "session_id": "...",
      "title": "My research chat",
      "created_at": "2024-04-11T10:30:00Z",
      "message_count": 12,
      "context_type": "project"
    }
  ]
}
```

#### `GET /sessions/{session_id}/history`
**Récupérer historique complet d'une session**
```json
Response:
{
  "messages": [
    {
      "id": "msg-id",
      "role": "user",
      "content": "Question?",
      "timestamp": "2024-04-11T10:32:00Z"
    },
    {
      "id": "msg-id-2",
      "role": "assistant",
      "content": "Answer...",
      "sources": ["doc-1", "doc-2"],
      "timestamp": "2024-04-11T10:32:05Z"
    }
  ]
}
```

#### `POST /sessions/{session_id}/rename`
**Renommer une session**
```json
Request:
{
  "new_title": "Updated chat title"
}

Response:
{
  "session_id": "...",
  "title": "Updated chat title"
}
```

---

### 💬 Conversation & Query

#### `POST /conversation` (Streaming)
**Envoyer une message et recevoir réponse en streaming**
```json
Request:
{
  "session_id": "550e8400-e29b-41d4",
  "query": "What is NLP?",
  "language": "en"
}

Response (text/event-stream):
data: {"token": "Natural", "type": "text_chunk"}
data: {"token": " Language", "type": "text_chunk"}
data: {"token": " Processing", "type": "text_chunk"}
data: {"sources": [{"id": "doc-1", "title": "NLP Basics", "score": 0.92}], "type": "metadata"}
data: {"token": "[DONE]", "type": "done"}
```

#### `POST /query`
**Requête rapide (non-conversationnelle)**
```json
Request:
{
  "query": "Define machine learning"
}

Response:
{
  "response": "Machine Learning is a subset of AI...",
  "sources": [{"id": "...", "score": 0.89}],
  "processing_time_ms": 234
}
```

---

### 📚 Document Management

#### `POST /documents/upload`
**Uploader un document pour indexation**
```form
file: <binary PDF/Image>
session_id: 550e8400-e29b-41d4

Response:
{
  "document_id": "doc-550e8400",
  "filename": "research.pdf",
  "status": "processing",
  "chunks_created": 0
}
```

#### `GET /documents/status/{document_id}`
**Vérifier statut d'indexation d'un document**
```json
Response:
{
  "document_id": "doc-550e8400",
  "status": "ready",
  "chunks_indexed": 45,
  "processing_time_s": 12.5,
  "indexed_at": "2024-04-11T10:35:00Z"
}
```

#### `GET /documents/list`
**Lister documents de l'utilisateur**
```json
Response:
{
  "documents": [
    {
      "document_id": "doc-550e8400",
      "filename": "research.pdf",
      "chunks": 45,
      "indexed_at": "2024-04-11T10:35:00Z"
    }
  ]
}
```

---

### 🔍 Advanced Search

#### `POST /search/platform`
**Recherche dans contenu de la plateforme (projet, ressources, etc.)**
```json
Request:
{
  "query": "NLP research papers",
  "filters": {
    "content_type": "resource",
    "date_from": "2024-01-01"
  },
  "limit": 10
}

Response:
{
  "results": [
    {
      "id": "res-550e8400",
      "title": "Advanced NLP Techniques",
      "content_type": "resource",
      "relevance_score": 0.94,
      "source_url": "/resources/550e8400"
    }
  ],
  "total": 45,
  "search_time_ms": 123
}
```

#### `POST /search/legal`
**Recherche spécialisée dans documents juridiques**
```json
Request:
{
  "query": "Copyright regulations",
  "jurisdiction": "Algeria"
}

Response:
{
  "results": [
    {
      "id": "legal-550e8400",
      "title": "Algerian Copyright Law Article 5",
      "relevance": 0.97,
      "excerpt": "..."
    }
  ]
}
```

#### `POST /search/web`
**Recherche web (Exa ou Tavily)**
```json
Request:
{
  "session_id": "550e8400-e29b-41d4",
  "query": "Latest NLP advances 2024",
  "provider": "tavily"  // or "exa"
}

Response:
{
  "results": [
    {
      "title": "Article Title",
      "url": "https://...",
      "snippet": "...",
      "date": "2024-04-10"
    }
  ],
  "search_time_ms": 456
}
```

---

## Modèles de données

### 🗄️ Base de données (PostgreSQL)

#### Table: `chatbot_chatsession`
```sql
CREATE TABLE chatbot_chatsession (
  id UUID PRIMARY KEY,
  user_id INT REFERENCES auth_user(id) ON DELETE CASCADE,
  fastapi_session_id VARCHAR(255) UNIQUE,
  title VARCHAR(200),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE,
  is_pinned BOOLEAN DEFAULT FALSE,
  content_type VARCHAR(50),           -- e.g., "project", "resource"
  object_id VARCHAR(255),             -- e.g., project UUID
  content_title VARCHAR(500),         -- e.g., project name
  has_documents BOOLEAN DEFAULT FALSE,
  document_filename VARCHAR(255),
  
  INDEX(user_id, updated_at),
  INDEX(fastapi_session_id)
);
```

#### Table: `chatbot_chatmessage`
```sql
CREATE TABLE chatbot_chatmessage (
  id UUID PRIMARY KEY,
  session_id UUID REFERENCES chatbot_chatsession(id) ON DELETE CASCADE,
  message_type VARCHAR(10),           -- 'user', 'bot', 'system', 'error'
  content TEXT,
  timestamp TIMESTAMP DEFAULT NOW(),
  source VARCHAR(50),                 -- e.g., 'user_input', 'qdrant', 'elasticsearch'
  language VARCHAR(10) DEFAULT 'en',  -- 'en', 'fr', 'ar'
  is_pinned BOOLEAN DEFAULT FALSE,
  
  INDEX(session_id, timestamp)
);
```

#### Table: `chatbot_chatfeedback`
```sql
CREATE TABLE chatbot_chatfeedback (
  id UUID PRIMARY KEY,
  session_id UUID REFERENCES chatbot_chatsession(id) ON DELETE CASCADE,
  message_id UUID REFERENCES chatbot_chatmessage(id) ON DELETE CASCADE,
  rating INT CHECK (rating >= 1 AND rating <= 5),  -- 1-5 stars
  comment TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 🔍 Modèles en mémoire (Redis)

#### Session Storage
```json
{
  "session:{session_id}": {
    "user_id": "123",
    "created_at": "2024-04-11T10:30:00Z",
    "messages": [
      {
        "role": "user",
        "content": "How does RAG work?",
        "timestamp": "2024-04-11T10:32:00Z"
      },
      {
        "role": "assistant",
        "content": "RAG combines retrieval and generation...",
        "sources": ["doc-1"],
        "timestamp": "2024-04-11T10:32:05Z"
      }
    ],
    "context": null,
    "ttl": 3600  // 1 hour
  }
}
```

#### User Rate-Limiting
```json
{
  "ratelimit:{user_id}:{endpoint}": "12",  // Current count
  "ttl": 60  // seconds
}
```

#### Embedding Cache
```json
{
  "embedding:{text_hash}": {
    "vector": [0.123, 0.456, ..., 0.789],  // 1024 dims
    "model": "BAAI/bge-m3",
    "timestamp": "2024-04-11T10:30:00Z"
  }
}
```

### 📊 Modèles Qdrant (Vectoriel)

#### Collection: `platform_resources`
```json
{
  "id": "chunk-550e8400-01",
  "vector": [0.123, 0.456, ..., 0.789],  // 1024 dims
  "payload": {
    "document_id": "doc-550e8400",
    "filename": "research_paper.pdf",
    "source_type": "user_document",
    "chunk_index": 1,
    "page_number": 5,
    "text_content": "Natural Language Processing...",
    "language": "en",
    "user_id": "123",
    "indexed_at": "2024-04-11T10:35:00Z"
  }
}
```

#### Collection: `legal_knowledge`
```json
{
  "id": "legal-article-1523",
  "vector": [0.234, 0.567, ..., 0.890],
  "payload": {
    "source_type": "legal_document",
    "jurisdiction": "Algeria",
    "document_id": "law-2024-05",
    "article": "5",
    "section": "Copyright",
    "text_content": "Copyright protection extends...",
    "citation": "Algerian Copyright Law Article 5"
  }
}
```

---

## Services protagonistes

### 🧠 Chat Logic Service

**Fichier** : `services/chat_logic.py`

Responsibilités :
1. Classification d'intentions (Intent → Handler routing)
2. Gestion d'historique (load, append, summarize)
3. Orchestration RAG complète
4. Streaming de réponses
5. Gestion des erreurs et fallbacks

**Procédure principale** :
```python
async def process_query(session_id, user_query, language='en'):
    # 1. Charger la session depuis Redis
    session = await session_service.get_session(session_id)
    
    # 2. Classifier l'intention
    intent = await classify_intent(user_query)  # groq llama-3.1-8b
    
    # 3. Router vers le bon handler
    if intent == 'conversation':
        return await handle_conversation(session, user_query)
    elif intent == 'platform_search':
        return await handle_platform_search(user_query)
    # ...
    
    # 4. Streaming de réponse
    async for token in response_stream:
        yield token
    
    # 5. Sauvegarder dans PostgreSQL
    await db.save_message(session_id, message)
```

### 💾 Memory Service (Session Management)

**Fichier** : `services/memory.py`

Responsibilités :
1. Gestion du cycle de vie des sessions
2. Stockage/rappel d'historique
3. Summarization automatique de long contexte
4. Gestion TTL (Time-To-Live)

**Flux** :
```python
async def append_message(session_id, role, content, source=None):
    # Charger session Redis
    session = redis.get(f"session:{session_id}")
    
    # Ajouter message
    session.messages.append({
        "role": role,
        "content": content,
        "timestamp": now(),
        "source": source
    })
    
    # Si > 12 messages, summarize
    if len(session.messages) > SUMMARY_THRESHOLD:
        summary = await summarize_history(session.messages[:6])
        session.messages = [summary] + session.messages[6:]
    
    # Sauvegarder Redis (TTL = 1 heure)
    redis.setex(f"session:{session_id}", 3600, serialize(session))
    
    # Sauvegarder PostgreSQL
    await db.save_message(session_id, role, content)
```

### 📄 Document Service

**Fichier** : `services/documents/`

Pipelines :
1. **Upload & Validation** (`upload.py`)
   - Vérif. taille, type content
   - Stockage secure (disque + metadata BD)

2. **Extraction** (`extractors/`)
   - PDFs → PyMuPDF
   - Images/scans → Tesseract OCR
   - Docs Word → python-docx

3. **Chunking** (`chunking.py`)
   - Token count + sentence boundaries
   - Overlap pour contexte
   - Max chunks/doc

4. **Embedding** (`embeddings.py`)
   - BGE-M3 encoding
   - Batch processing
   - Cache pour réutilisation

5. **Indexing** (`indexing.py`)
   - Vector → Qdrant
   - Full-text → Elasticsearch
   - BM25 → in-memory

### 🔎 Retrieval Service (Hybrid Search)

**Fichier** : `services/retrieval/`

Pipeline hybride :
```python
async def hybrid_search(query, top_k=5, threshold=0.65):
    # 1. Vector search (Qdrant)
    query_embedding = encode(query)  # BGE-M3
    vector_results = qdrant.search(
        collection='platform_resources',
        vector=query_embedding,
        limit=top_k,
        threshold=threshold
    )
    
    # 2. Full-text search (Elasticsearch)
    text_results = elasticsearch.search(
        query=query,
        size=top_k
    )
    
    # 3. Fusion (RRF)
    fused = reciprocal_rank_fusion(vector_results, text_results)
    
    return fused[:top_k]
```

### 🌐 Platform Query Service

**Fichier** : `services/platform_queries.py`

Requêtes intelligentes sur contenu Sanad :
- Projets, Ressources, Événements, Institutions
- Filtrage par date, catégorie, langue
- Pagination automatique
- Ranking par pertinence

---

## Pipeline RAG complet

### 🔄 Étapes détaillées

#### **Étape 1 : Encoding de la requête**
```python
# User query
query = "What are the best practices for NLP preprocessing?"

# Encode with BGE-M3
embedding = embedding_service.encode(query)
# Output: [0.123, 0.456, ..., 0.789]  (1024 dims)

# Check cache
cached = redis.get(f"embedding:{hash(query)}")
if cached:
    embedding = cached  # Réutiliser
else:
    redis.setex(f"embedding:{hash(query)}", 86400, embedding)  # Cache 24h
```

#### **Étape 2 : Récupération vectorielle (Qdrant)**
```python
# Top-K similarity search with threshold
results = qdrant.search(
    collection_name="platform_resources",
    query_vector=embedding,
    limit=10,
    threshold=0.65,  # Min similarity score
    with_payload=True
)

# Results:
# [
#   {id: "chunk-1", score: 0.94, payload: {...}},
#   {id: "chunk-2", score: 0.88, payload: {...}},
#   ...
# ]
```

#### **Étape 3 : Recherche full-text (Elasticsearch)**
```python
es_results = elasticsearch.search(
    index="platform_resources",
    query={
        "multi_match": {
            "query": query,
            "fields": ["text_content^2", "title"],
            "analyzer": "arabic_light"
        }
    },
    size=10
)

# Results with BM25 scores:
# {
#   "hits": [
#     {"_score": 12.5, "_source": {...}},
#     {"_score": 9.8, "_source": {...}},
#     ...
#   ]
# }
```

#### **Étape 4 : Fusion RRF (Reciprocal Rank Fusion)**
```python
def reciprocal_rank_fusion(vector_results, text_results, k=60):
    """
    Combine vector + text rankings using RRF formula:
    RRF(d) = Σ 1/(k + rank_i(d))
    """
    fused_scores = {}
    
    # Vector scores (rank by score desc)
    for rank, result in enumerate(sorted(vector_results, key=lambda x: x['score'], reverse=True)):
        doc_id = result['id']
        fused_scores[doc_id] = fused_scores.get(doc_id, 0) + 1 / (k + rank)
    
    # Text scores
    for rank, result in enumerate(text_results):
        doc_id = result['_id']
        fused_scores[doc_id] = fused_scores.get(doc_id, 0) + 1 / (k + rank)
    
    # Sort and return top-k
    return sorted(
        fused_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]  # Top 5

# Example output:
# [
#   ('chunk-1', 0.025),  # Combined score
#   ('chunk-5', 0.021),
#   ('chunk-2', 0.018),
#   ...
# ]
```

#### **Étape 5 : Construction du contexte**
```python
def build_rag_context(fused_results, chunked_sources):
    """Format retrieved chunks with metadata for LLM"""
    
    context_parts = []
    for rank, (doc_id, score) in enumerate(fused_results[:5], 1):
        chunk = chunked_sources[doc_id]
        
        context_parts.append(f"""
[Reference {rank}]
Source: {chunk['filename']} (Page {chunk['page_number']})
Relevance Score: {score:.2%}
Content:
{chunk['text_content']}
---
        """)
    
    return "\n".join(context_parts)

# Output:
"""
[Reference 1]
Source: nlp_guide.pdf (Page 5)
Relevance Score: 94.2%
Content:
Preprocessing is the first step in NLP pipelines. It involves:
1. Tokenization - splitting text into tokens
2. Normalization - converting to lowercase, removing accents
3. Stop word removal - filtering common words
...
---

[Reference 2]
Source: research_paper_2024.pdf (Page 12)
Relevance Score: 88.0%
Content:
Modern preprocessing using transformers...
...
"""
```

#### **Étape 6 : Assemblage du prompt**
```python
prompt = f"""
You are an expert in Natural Language Processing and Arabic language technologies.
Your goal is to provide accurate, helpful, and well-reasoned answers.

---
RETRIEVED CONTEXT (from platform knowledge base):

{rag_context}

---
CONVERSATION HISTORY (last 3 exchanges):

User: "How does tokenization work?"
Assistant: "Tokenization is the process of breaking text into individual elements..."

---
USER QUESTION:
{user_query}

---
INSTRUCTIONS:
1. Use the retrieved context to inform your answer
2. If the context directly answers the question, cite it
3. If context is insufficient, acknowledge and explain what you can deduce
4. Be specific, provide examples when relevant
5. Respond in {language} language
6. Format lists clearly with bullet points or numbers

RESPONSE:
"""
```

#### **Étape 7 : Génération (Groq API Streaming)**
```python
# Send prompt to Groq API with streaming
async def stream_response(prompt):
    async with AsyncClient() as client:
        async with client.stream(
            method="POST",
            url="https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
                "temperature": 0.7,
                "top_p": 0.9,
                "stream": True
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk = json.loads(line[6:])
                    if chunk['choices'][0]['delta'].get('content'):
                        token = chunk['choices'][0]['delta']['content']
                        yield token  # Send to client via SSE
```

#### **Étape 8 : Post-traitement et vérification de fidélité**
```python
async def verify_faithfulness(original_query, retrieved_context, generated_response):
    """
    Check if response is grounded in context.
    Returns: 'faithful' or 'unfaithful'
    """
    
    verify_prompt = f"""
    Given the original question, retrieved context, and generated response,
    is the response faithfully grounded in the context?
    
    Question: {original_query}
    
    Context: {retrieved_context}
    
    Response: {generated_response}
    
    Answer only: 'faithful' or 'unfaithful'
    """
    
    # Use fast, small model for verification
    result = await groq_small_llm.complete(
        model="llama-3.1-8b-instant",
        prompt=verify_prompt,
        max_tokens=10
    )
    
    return "faithful" in result.lower()

# Store verdict with message
feedback = {
    "response_id": response_id,
    "faithful": is_faithful,
    "score": 1.0 if is_faithful else 0.0,
    "verified_at": now()
}
await db.save_feedback(feedback)
```

#### **Étape 9 : Stockage dans PostgreSQL**
```python
# Save conversation to persistent database
message_record = ChatMessage(
    session_id=session_id,
    message_type='bot',
    content=full_response,
    source='rag_pipeline',
    language=language,
    metadata={
        "retrieved_sources": [doc['filename'] for doc in retrieved],
        "retrieval_scores": [doc['score'] for doc in retrieved],
        "model_used": "llama-3.3-70b",
        "processing_time_ms": elapsed_time,
        "faithfulness": is_faithful
    }
)
await db.session.add(message_record)
await db.session.commit()

# Update session last activity
session.updated_at = now()
await db.session.commit()
```

---

## Configuration et déploiement

### 🔧 Variables d'environnement

```bash
# Groq API
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
GROQ_INTERNAL_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx  # Peut être le même ou différent
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_INTERNAL_MODEL=llama-3.1-8b-instant
GROQ_MAX_TOKENS=2048
GROQ_TEMPERATURE=0.7

# Qdrant Vector DB
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_PREFER_GRPC=True
QDRANT_API_KEY=  # Optional

# Elasticsearch
ELASTICSEARCH_HOST=http://elasticsearch:9200

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/chatbot_db

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024

# Search Parameters
TOP_K_RESULTS=5
SIMILARITY_THRESHOLD=0.65

# Rate Limiting
MAX_REQUESTS_PER_MINUTE=30

# Document Processing
MAX_UPLOAD_SIZE_MB=20
CHUNK_SIZE=512
CHUNK_OVERLAP=64
MAX_CHUNKS_PER_DOC=500

# Chat Memory
MAX_HISTORY_MESSAGES=20
HISTORY_SUMMARY_THRESHOLD=12
TOKEN_BUDGET_HISTORY=1500
TOKEN_BUDGET_SUMMARY=500

# Web Search (Optional)
EXA_API_KEY=  # Exa search API key
EXA_ENABLED=False
TAVILY_API_KEY=  # Tavily search API key
TAVILY_ENABLED=False

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
```

### 🐳 Docker Compose

```yaml
services:
  fastapi_chatbot:
    build:
      context: ./fastapi_chatbot
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/chatbot
      - QDRANT_HOST=qdrant
      - ELASTICSEARCH_HOST=http://elasticsearch:9200
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./fastapi_chatbot/app:/app/app
    networks:
      - sanad_network

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - sanad_network

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -q green"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - sanad_network

volumes:
  qdrant_data:
  elasticsearch_data:

networks:
  sanad_network:
    driver: bridge
```

---

## Améliorations futures

### 🎯 Court terme (1-3 mois)
- [ ] **Fine-tuning du modèle d'embeddings** sur données Sanad
  - Améliore la pertinence du retrieval
  - Spécialisation pour domaines académiques/légaux
- [ ] **Caching sémantique** pour requêtes répétées
  - Réduit latence + coûts LLM
- [ ] **Multi-turn dialogue** amélioré
  - Meilleure gestion de contexte long
  - Summarization plus intelligente
- [ ] **Feedback loop** actif  
  - Capturer user feedback sur qualité
  - Fine-tune LLM interne sur feedback

### 🚀 Moyen terme (3-6 mois)
- [ ] **Migration vers Kubernetes** pour scalabilité
  - Auto-scaling des workers
  - Gestion des ressources GPU
- [ ] **Message broker** (RabbitMQ/Kafka)
  - Découplage des services
  - Meilleure fiabilité
- [ ] **LLM local** en option
  - Llama 2 13B ou Mistral 7B
  - Inférence on-premise
- [ ] **Multimodality** : support images/vidéos
  - Vision transformers pour images
  - Captions automatiques pour vidéos

### 💎 Production (6-12 mois)
- [ ] **Multitenancy** complète
  - Isolation données par tenant
  - Billing par usage
- [ ] **Advanced RAG** 
  - Query decomposition multi-hop
  - Graph retrieval
  - Temporal reasoning
- [ ] **Human-in-the-loop**
  - Expert validation pipeline
  - Active learning
- [ ] **Observability** niveau production
  - Tracing distribué (Jaeger)
  - Metrics détaillées (Prometheus)
  - Alerting intelligent

---

## Conclusion

Le **chatbot intelligent Sanad** représente une convergence de technologies modernes (LLMs, vector search, full-text indexing) dans une architecture **modulaire, scalable et maintenable**. Chaque composant a un rôle clairement défini, permettant des évolutions futures sans refondre l'existant.

Les points clés du système :
1. **RAG avancé** pour grounding des réponses
2. **Recherche hybride** (vector + full-text)
3. **Multi-langage** natif (arabe, français, anglais)
4. **Streaming** pour UX responsive
5. **Persistance complète** (contexte, feedback, historique)
6. **Scalabilité** via async, caching, et microservices

---

**Document généré** : Avril 2026  
**Version** : 4.0.0  
**Auteurs** : BETTAYEB M.A., MEZIANE L.L., DAHMANE Y., BEZZA A.  
**Superviseur** : Dr. BERKANI Lamia
