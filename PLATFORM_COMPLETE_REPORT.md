# 📊 ARABIC NLP RESEARCH PLATFORM - COMPLETE COMPREHENSIVE REPORT

**Date:** April 10, 2026  
**Status:** Production Ready  
**Version:** 2.0+  
**Report Level:** EXHAUSTIVE - EVERYTHING

---

## 🎯 Executive Summary

**Plateforme_NLP** is a **world-class, production-grade Arabic Natural Language Processing research platform** serving as a complete digital ecosystem for Arabic NLP researchers, academics, and practitioners. 

### Platform Purpose
A comprehensive hub where the global Arabic NLP research community can:
- Discover and access research resources (papers, datasets, tools)
- Collaborate on research projects
- Participate in discussions and share knowledge
- Publish and share findings
- Connect with researchers and institutions
- Stay updated on scientific events and opportunities

### Key Statistics
- **15+ Django Applications** for all major features
- **30+ Database Models** with rich relationships
- **8 Elasticsearch Document Types** for advanced search
- **4+ Languages** (Arabic, English, French, Spanish)
- **1000+ Dimensional** vector embeddings
- **6 Resource Types** (Publications, Datasets, Tools, Courses, Events, Institutions)
- **Production-Grade Infrastructure** with monitoring & scalability
- **Enterprise-Level Security** with 2FA, blocking, and moderation

---

## 🏗️ Complete Architecture Overview

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend Framework** | Django 5.1+ | Web application & UI |
| **API Server** | FastAPI 0.115.0 | AI/Chatbot backend |
| **WSGI Server** | Uvicorn + Gunicorn | Request handling |
| **Relational Database** | PostgreSQL | Structured data storage |
| **Vector Database** | Qdrant 1.12.1 | Semantic search & embeddings |
| **Search Engine** | Elasticsearch 8.11.0 | Full-text search & indexing |
| **Cache** | Redis | Session, cache, message broker |
| **Task Queue** | Celery 5.4.0 | Async processing |
| **LLM Provider** | Groq API | AI/Chatbot intelligence |
| **Embeddings** | BAAI/bge-m3 (1024-dim) | Semantic vectors |
| **PDF Processing** | Docling (IBM) | Document extraction |
| **Monitoring** | Prometheus + Grafana | Observability |
| **Containerization** | Docker & Docker Compose | Deployment |
| **Reverse Proxy** | Nginx | Load balancing |
| **Web Scraping** | BeautifulSoup, Playwright | Automated data collection |

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│         CLIENT LAYER (Browser)                          │
│  ├─ Web Interface (Django Templates)                    │
│  ├─ Static Assets (CSS, JS, Images)                     │
│  └─ Real-time Sockets (WebsocketS)                     │
└──────────────────┬──────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────┐
│    REVERSE PROXY & CDN (Nginx)                          │
│  ├─ Static file serving                                 │
│  ├─ Load balancing                                      │
│  ├─ SSL/TLS termination                                 │
│  └─ Rate limiting                                       │
└──────────────────┬──────────────────────────────────────┘
                   ↓
      ┌────────────┴────────────┐
      ↓                         ↓
┌─────────────────┐    ┌──────────────────┐
│  Django App     │    │  FastAPI Service │
│  (Port 8000)    │    │  (Port 8001)     │
│  ├─ Templates   │    │  ├─ RAG Pipeline │
│  ├─ Views       │    │  ├─ Chatbot      │
│  └─ ORM Models  │    │  └─ AI Logic     │
└────────┬────────┘    └────────┬─────────┘
         └────────────┬─────────┘
                      ↓
      ┌───────────────┴────────────────┐
      ↓                                ↓
┌─────────────────────┐     ┌──────────────────────┐
│  Celery Workers     │     │  Background Tasks    │
│  (Async Jobs)       │     │  ├─ Scraping         │
│  ├─ Scraping        │     │  ├─ Indexing        │
│  ├─ Embeddings      │     │  ├─ Enrichment      │
│  └─ Processing      │     │  └─ Notifications   │
└─────────────────────┘     └──────────────────────┘
         └────────────┬────────────┘
                      ↓
     ┌────────────────┴─────────────────┐
     ↓                 ↓                 ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ PostgreSQL   │ │   Qdrant     │ │Elasticsearch │
│  Database    │ │  Vector DB   │ │   Search     │
│              │ │              │ │              │
│ ├─Accounts   │ │ ├─Embeddings │ │ ├─Users      │
│ ├─Resources  │ │ ├─Vectors    │ │ ├─Papers     │
│ ├─Projects   │ │ ├─Docs       │ │ ├─Projects   │
│ └─Messages   │ │ └─Corpus     │ │ └─Events     │
└──────────────┘ └──────────────┘ └──────────────┘
```

---

## 📚 COMPLETE FEATURE SET (15+ Applications)

### 1️⃣ **User Management & Authentication** 👥

**Module:** `accounts/` **Status:** Core, Fully Featured

#### A. User Profiles
- **Multi-language Names:** Arabic, English, localized
- **Bios/Biographies:** Bilingual support
- **Avatar/Profile Pictures:** Image upload
- **Email-based Authentication:** Primary login method
- **Email Verification:** 6-digit code verification
- **User Status:** Pending → Active → Blocked states
- **18+ AI Specialization Fields:**
  - Machine Learning, Deep Learning, NLP
  - Computer Vision, Reinforcement Learning
  - AI Ethics, Robotics, Neural Networks
  - AI Security, Healthcare, Finance, Education
  - Transportation, Agriculture, Energy, Manufacturing
  - Fundamental AI Research, Other

#### B. Two-Factor Authentication (2FA) 🔐
- **OTP via Email:** 6-digit codes
- **Mandatory on Login:** Triggers on signup/login
- **Redis-backed:** Fast OTP storage & validation
- **Timeout Protection:** Time-limited codes
- **Signal-driven:** Post-login & post-signup hooks

#### C. User Network & Relationships
- **Follow System:** Track researchers & experts
- **Friendship Model:** Relationship management
- **Blocking System:** Block/hide users
  - Bidirectional blocking
  - Complete content hiding from blocked users
  - Escape blocked_user_ids_for() utility
- **Follow Requests:** Accept/reject followers
- **Network Invitations:** Manage connections
- **Online Status Visibility:** Configurable presence

#### D. User Experience Tracking
- **Work Experience:** Job titles, companies, dates
- **Education Experience:** Schools, degrees, dates
- **Experience Types:** 
  - Work Experience
  - Education/Training
  - Certification
  - Research Project
  - Publication
- **Timeline Management:** Validations & constraints

#### E. Professional Details
- **Institution Affiliation:** Link to research institution
- **Social Media Links:** LinkedIn, Twitter, Facebook
- **Verification Badge:** Verified researcher status
- **Profile Completeness:** Tracked & encouraged
- **Contribution Stats:** Publications, projects, resources

#### F. Account Security
- **Password Hashing:** Industry standard (PBKDF2)
- **Session Management:** Django sessions + custom timeouts
- **Login Attempt Tracking:** Rate limiting on failures
- **Account Locking:** After N failed attempts
- **IP Blocking:** Suspicious IP detection
- **Brute Force Protection:** Exponential backoff

---

### 2️⃣ **Resource Management Library** 📚

**Module:** `resources/` **Status:** Core, Comprehensive

A rich ecosystem with 6 resource types, all with multilingual support and approval workflows.

#### A. Publications & Research Papers 📄
**Model:** `Document`

- **Document Types:**
  - Research Paper
  - Journal Article
  - Conference Paper
  - Thesis/Dissertation
  - Technical Report
  - Book Chapter
  - Preprint (ArXiv)

- **Metadata:**
  - DOI (Digital Object Identifier)
  - Journal Name
  - Authors & Author List
  - Publication Date & Year
  - Abstract & Summary
  - Keywords & Tags
  - PDF/DOCX file uploads
  - Access links (external)

- **Features:**
  - Full-text search via Elasticsearch
  - ArXiv ID tracking
  - Citation counting
  - View tracking & popularity metrics
  - Author tracking
  - Multilingual content
  - Approval workflow (pending→approved/rejected)

#### B. Datasets & Corpora 🗂️
**Model:** `Corpus`

- **Dataset Information:**
  - Corpus name & descriptions
  - Size metrics: Word count, document count
  - Language support (AR, EN, FR, ES)
  - Domain classification
  - Data format (TXT, CSV, JSON, XLSX)

- **Corpus Details:**
  - Annotation format & standards
  - Collection methodology
  - License information
  - Temporal coverage
  - Source attribution
  - Download links to external sources

- **Metadata:**
  - Language specifications
  - Quality metrics
  - Version tracking
  - Update history
  - Related papers

#### C. NLP Tools & Software 🛠️
**Model:** `NLPTool`

- **Tool Categories & Types:**
  - Tokenization Tools
  - Stemming & Lemmatization
  - Named Entity Recognition (NER)
  - Part-of-Speech (POS) Tagging
  - Sentiment Analysis Tools
  - Machine Translation Systems
  - Text Classification Systems
  - Parsing Tools
  - Information Extraction

- **Tool Details:**
  - Version tracking (semantic versioning)
  - Documentation links (official)
  - GitHub/repository links
  - Installation instructions
  - API documentation
  - Language support specifications
  - Performance benchmarks
  - Last updated date
  - License type
  - Author/maintainer info

#### D. Online Courses 🎓
**Model:** `Course`

- **Course Information:**
  - Course title & multilingual descriptions
  - Level indicators: Beginner, Intermediate, Advanced
  - Duration & commitment time
  - Prerequisites
  - Learning outcomes

- **Course Delivery:**
  - Format: Online, In-person, Hybrid
  - Instructor/author info
  - Enrollment links
  - Cost/Free indicators
  - Certificate availability
  - Language of instruction

- **Content:**
  - Topics covered
  - Module structure
  - Assignments & quizzes
  - Video lectures (links)

#### E. Events & Conferences 📅
**Model:** `Event` (see separate section below)

#### F. Institutions & Organizations
**Model:** `Institution` (see separate section below)

#### General Features (All Resources):
- **Multilingual Support:**
  - Bilingual titles (AR/EN)
  - Bilingual descriptions
  - Language field
  - Auto-detection

- **Approval Workflow:**
  - Pending → Approved → Published
  - Pending → Rejected (with reason)
  - Admin review queue
  - Rejection reason tracking
  - Resubmission capability

- **Access Control:**
  - Creator ownership
  - Edit permissions
  - Delete permissions
  - Share with others
  - Public/private visibility

- **Engagement Metrics:**
  - View counter
  - Download counter
  - Citation counter
  - Like/favorite system
  - Comment/review system

- **Tagging & Discovery:**
  - Keyword tagging
  - Category classification
  - Domain assignment
  - Full-text search
  - Faceted search
  - Related resources

---

### 3️⃣ **Project Management & Collaboration** 🚀

**Module:** `projects/` **Status:** Core, Feature-Rich

#### A. Project Creation & Management
- **Project Types:**
  - Research Projects
  - Development Projects
  - Data Collection Projects
  - Evaluation Projects
  - Publication Projects

- **Project Information:**
  - Bilingual titles (AR/EN)
  - Detailed descriptions
  - Project goals & objectives
  - Expected outcomes
  - Timeline & milestones

#### B. Project Organization
- **Institutional Context:**
  - Linked institution
  - Department/group
  - Research fund/grant info

- **Categorization:**
  - Research domains (M2M)
  - NLP methods used (M2M)
  - Supported languages
  - Related tools & resources

#### C. Project Status Tracking
- **Project States:**
  - Planned (future)
  - Ongoing (active)
  - Completed (finished)
  - Archived (historical)

- **Approval Workflow:**
  - Pending institutional review
  - Approved by institution
  - Rejected with reason
  - Published to community

#### D. Team Management
- **Project Members:**
  - Project owner/creator
  - Team members (multiple)
  - Collaborators
  - Advisors/supervisors

- **Membership States:**
  - Pending (invitation sent)
  - Accepted (active member)
  - Declined (rejected)
  - Removed (deleted)

- **Roles & Permissions:**
  - Owner (full control)
  - Member (contribute)
  - Viewer (read-only)

- **Invitations:**
  - Invite by email
  - Accept/decline workflow
  - Bulk invitations
  - Request to join

#### E. Resource Linking
- **Link to Resources:**
  - Datasets & Corpora
  - Papers & Publications
  - NLP Tools
  - Courses & Materials
  - Related Projects

#### F. Project Chatroom 💬
**Module:** `project_chatroom/`

Dedicated real-time communication space for project teams:

- **Project Chat Features:**
  - Per-project private chatrooms
  - Real-time messaging
  - Message persistence
  - Edit history
  - File attachments
  - Image uploads

- **Message Management:**
  - Threaded conversations
  - User mentions (@username)
  - Quote/reply functionality
  - Message timestamps
  - Viewed status

- **File Attachments:**
  - Image support
  - Document uploads
  - Size limits
  - Virus scanning
  - Thumbnail generation

- **Access Control:**
  - Only project members
  - Invitation-based
  - Leave group option

---

### 4️⃣ **Events & Conferences** 📅

**Module:** `events/` **Status:** Core, Fully Featured

#### A. Event Types
- **Conference** - Large academic gatherings
- **Workshop** - Focused training sessions
- **Seminar** - Expert presentations
- **Call for Papers** - Publication opportunities
- **Hackathon** - Coding competitions
- **Webinar** - Online presentations
- **Other** - Custom event types

#### B. Event Information
- **Multilingual Details:**
  - Bilingual titles (AR/EN)
  - Bilingual descriptions
  - Multiple language support

- **Event Metadata:**
  - Start & end date/time
  - Deadline for submissions/registration
  - Location (physical address)
  - Online link (if hybrid/online)
  - Registration link
  - Contact information

#### C. Classification
- **Domain Classification:**
  - Natural Language Processing
  - Speech Processing
  - Artificial Intelligence
  - Arabic Language
  - Linguistics
  - Machine Translation
  - Sentiment Analysis
  - Text Summarization
  - Other domains

- **Language of Event:**
  - Arabic
  - English
  - French
  - Other

#### D. Event Sources
- **Automatic Scraping:** From EDAS, WikiCFP, etc.
- **Manual Submission:** Community contributions
- **API Integration:** Direct imports

#### E. Approval & Visibility
- **Status Workflow:**
  - Pending (awaiting review)
  - Approved (visible to all)
  - Rejected (hidden, with reason)

- **Visibility Control:**
  - Public events
  - Featured events
  - Pinned events

#### F. Engagement
- **Registrations:** Attendance tracking
- **Comments:** Community discussion
- **Sharing:** Share to followers
- **Bookmarking:** Save for later

---

### 5️⃣ **Institutions & Organizations** 🏛️

**Module:** `institutions/` **Status:** Core

#### A. Institution Profiles
- **Institution Information:**
  - Official name
  - Acronym/shortname
  - Country & city location
  - Website URL
  - Contact information
  - Description & mission

- **Categories:**
  - University
  - Research Center
  - Company/Industry
  - NGO
  - Government
  - Other

#### B. Researcher Affiliation
- **Affiliation Linking:**
  - Users linked to institutions
  - Department/group tracking
  - Position tracking

#### C. Institutional Content
- **Track Contributions:**
  - Publications by institution
  - Datasets created
  - Tools developed
  - Projects conducted
  - Courses offered

#### D. Institution Admin
- **Management Tools:**
  - Verify institutional members
  - Approve institutional contributions
  - Institute dashboard
  - Member management

---

### 6️⃣ **Forum & Discussion System** 💬

**Module:** `forum/` **Status:** Core, Community-Focused

#### A. Discussion Topics
- **Topic Management:**
  - Create topics/threads
  - Bilingual titles (AR/EN)
  - Detailed descriptions
  - Multiple language support

- **Topic States:**
  - Open (accepting replies)
  - Closed (read-only)
  - Pinned (always visible)
  - Featured (highlighted)

#### B. Topic Moderation
- **Approval Workflow:**
  - Pending (awaiting review)
  - Approved (visible)
  - Rejected (hidden, with reason)
  - Rejected (moderation)

- **Moderation Actions:**
  - Delete topics
  - Lock topics
  - Pin topics
  - Move topics
  - Merge topics

#### C. Topic Relations
- **Linking:**
  - Related to Projects
  - Related to Events
  - Related to News/Posts
  - Cross-reference

#### D. Community Engagement
- **Discussions:**
  - Topic replies (comments)
  - Nested conversations
  - User mentions
  - Quote replies

---

### 7️⃣ **Q&A & News Feed** 📰

**Module:** `QA/` / `feed/` **Status:** Core

#### A. Questions & Answers
- **Question Models:**
  - Title
  - Detailed description
  - Tags/keywords
  - Answer count
  - View count

- **Answer System:**
  - Multiple answers per question
  - Ranking/voting
  - Accepted answer marking
  - Comment on answers

#### B. News & Posts
- **Post Types:**
  - **Paper** - Research paper announcement
  - **News** - Platform/community news
  - **Announcement** - Important updates
  - **Blog** - Blog post format

- **Post Details:**
  - Multilingual content (AR/EN)
  - Image/thumbnail
  - File attachments
  - Author info
  - Publication date
  - Metadata tags

- **Post Enrichment:**
  - ArXiv ID linking
  - DOI tracking
  - Source URL
  - Source name (where from)
  - Relevance scoring
  - Entity extraction (JSON)
  - Author info (JSON array)

- **Engagement:**
  - Like/favorite system
  - Comment system
  - Share functionality
  - View tracking
  - Slug-based URL

#### C. Moderation
- **Approval Status:**
  - Pending (review queue)
  - Approved (published)
  - Rejected (with reason)

---

### 8️⃣ **Direct Messaging** ✉️

**Module:** `direct_messages/` **Status:** Core

#### A. Private Messages
- **One-to-One Messaging:**
  - Send messages to users
  - Message history
  - Timestamps
  - Read status

- **Conversation Management:**
  - Conversation list
  - Search in messages
  - Archive conversations
  - Delete conversations

#### B. Features
- **Message Features:**
  - Edit sent messages
  - Delete messages
  - Forward messages
  - Report inappropriate messages

- **Notifications:**
  - New message alerts
  - Reply notifications
  - @mention notifications

---

### 9️⃣ **Sharing & Content Distribution** 🔗

**Module:** `sharing/` **Status:** Core

#### A. Share Model
- **Share Any Content:**
  - Share resources with users
  - Share projects
  - Share events
  - Share forum posts
  - Share Q&A answers

- **Share Details:**
  - Sender & receiver
  - Content snapshot (survives deletion)
  - Personal message with share
  - Share timestamp
  - Status tracking (sent/seen)

#### B. Share Replies
- **Threaded Discussion:**
  - Reply to shares (threaded)
  - Private discussion on shared content
  - Only sender/receiver can access
  - Comment on shared items

---

### 🔟 **Feed & Activity Stream** 🔔

**Module:** `feed/` **Status:** Core

#### A. Activity Feed
- **Real-time Activity:**
  - Resource publications
  - Project updates
  - Event announcements
  - Forum discussions
  - New members
  - Followed user activities

#### B. Content Types
- **Feed Items:**
  - New publications
  - New datasets
  - New projects
  - Event announcements
  - Forum topics
  - Comments & replies
  - Follow actions

---

### 1️⃣1️⃣ **Notifications System** 🔔

**Module:** `notifications/` **Status:** Core, Extensive

#### A. Notification Types (25+)
- **System & General:**
  - SYSTEM (general)

- **Content Moderation:**
  - CONTENT_APPROVED
  - CONTENT_REJECTED

- **Project Notifications:**
  - PROJECT_INVITATION
  - MEMBERSHIP_REQUEST
  - PROJECT_UPDATE
  - TASK_ASSIGNED
  - LEAVE_REQUEST

- **Community & Social:**
  - FOLLOW_REQUEST
  - COMMENT (on your content)
  - MESSAGE (direct message)

- **Event Notifications:**
  - EVENT_CREATED
  - EVENT_APPROVED

- **Academic Resources:**
  - RESOURCE_ADDED
  - TOOL_ADDED
  - CORPUS_UPDATE
  - RESEARCH_UPDATE

- **Forum & Q&A:**
  - FORUM_TOPIC
  - QA_ANSWER
  - QA_COMMENT
  - POST_APPROVED
  - BAN (moderation)

- **Institutional:**
  - INSTITUTION_UPDATE

#### B. Notification Features
- **Bilingual Support:**
  - Bilingual titles (AR/EN)
  - Bilingual messages (AR/EN)

- **Notification Management:**
  - Mark as read/unread
  - Read timestamp
  - Delete notifications
  - Archive notifications
  - Notification history

- **Interactive Notifications:**
  - Accept/reject options
  - Response tracking
  - Response date logging

#### C. Delivery Methods
- **In-app Notifications:**
  - Notification bell
  - Notification center
  - Unread count

- **Email Notifications:**
  - Optional email delivery
  - Digest emails
  - Configurable preferences

---

### 1️⃣2️⃣ **Search System** 🔍

**Module:** `search/` **Status:** Core, Advanced

#### A. Elasticsearch Integration
Full-text search across entire platform with 8 searchable entity types:

**Search Documents:**
1. **UserDocument** - Researchers, user profiles
2. **CourseDocument** - Educational courses
3. **ToolDocument** - NLP tools & software
4. **CorpusDocument** - Datasets & corpora
5. **ResourceDocument** - General resources
6. **ProjectDocument** - Research projects
7. **EventDocument** - Conferences & events
8. **InstitutionDocument** - Organizations

#### B. Search Features
- **Multi-field Search:**
  - Full-text across all fields
  - Title-specific search
  - Description search
  - Author search
  - Keyword search

- **Advanced Filtering:**
  - By resource type
  - By language
  - By domain/category
  - By date range
  - By institution
  - By author
  - By approval status

- **Faceted Search:**
  - Aggregations by type
  - Aggregations by language
  - Aggregations by domain
  - Dynamic facets

- **Ranking & Relevance:**
  - BM25 scoring
  - Keyword boosting
  - Recency boosting
  - Popularity boosting (views)

---

### 1️⃣3️⃣ **Taxonomy & Classification** 📊

**Module:** `taxonomy/` **Status:** Core

#### A. Research Domains
- **Domain Hierarchy:**
  - Parent-child relationships
  - Nested domains
  - Domain browsing

- **Domain Data:**
  - Bilingual names (EN/AR)
  - Slug for URLs
  - Descriptions (EN/AR)
  - Domain relationships

#### B. NLP Methods
- **Method Categories:**
  - Supervised learning
  - Unsupervised learning
  - Transfer learning
  - Deep learning specific
  - Rule-based
  - Hybrid approaches

- **Method Details:**
  - Bilingual names (EN/AR)
  - Slug identifiers
  - Descriptions

#### C. Datasets Reference
- **Dataset Tracking:**
  - HuggingFace integration
  - PapersWithCode integration
  - Language support
  - Bilingual descriptions

---

### 1️⃣4️⃣ **Web Scraping System** 🕷️

**Module:** `scraping/` **Status:** Advanced, Production-Grade

Complete automated data harvesting system (see detailed section below).

#### Features:
- 5 scraper categories (Events, Courses, Tools, Institutions, News)
- LLM-powered validation & enrichment
- Deduplication engine
- Circuit breaker resilience
- Archive.org fallback
- Full audit logging

---

### 1️⃣5️⃣ **AI/Chatbot Service** 🤖

**Module:** `fastapi_chatbot/` **Status:** Advanced, Core Intelligence

Advanced RAG-based conversational AI (see dedicated section below).

#### Features:
- Multi-turn conversations
- PDF analysis
- Intent classification
- Hybrid retrieval
- Faithfulness verification
- Session management

---

### 1️⃣6️⃣ **Admin & Management** 🛠️

**Module:** `pages/` **Status:** Core

#### A. Admin Dashboard
- **Statistics:**
  - User count & growth
  - Resource statistics
  - Project statistics
  - Activity metrics

- **Content Moderation:**
  - Approval queue
  - Rejection management
  - Appeal handling

- **User Management:**
  - User verification
  - User blocking
  - Status changes
  - Account suspension

#### B. Settings Management
**Module:** `settings/` **Status:** Core

- **Site Configuration:**
  - Site name & description
  - Logo/favicon
  - Maintenance mode

- **Feature Flags:**
  - Enable/disable registration
  - Enable/disable specific features
  - Social login toggles
  - Content moderation settings

- **Email Configuration:**
  - SMTP settings
  - Email templates
  - Notification preferences

---

## 🕷️ COMPLETE WEB SCRAPING SYSTEM

**Module:** `scraping/` **Status:** Production Grade

### Architecture

```
Web Sources
    ↓
┌─────────────────────────────────────┐
│  Scraper Manager (Orchestration)   │
│  ├─ Scheduling (Adaptive)          │
│  ├─ Checkpoint / Resume            │
│  └─ Rate Limiting                  │
└────────────┬────────────────────────┘
             ↓
    ┌────────┴────────┐
    ↓                 ↓
┌───────────┐    ┌─────────────┐
│  Category │    │  Specialized │
│ Dispatche │    │  Scrapers   │
└───────────┘    └─────────────┘
    ↓                 ↓
    └────────┬────────┘
             ↓
    ┌──────────────────────────┐
    │ HTTP/Playwright Layer    │
    │ ├─ Retry & Backoff       │
    │ ├─ User-Agent Rotation   │
    │ ├─ Proxy Support         │
    │ └─ Timeout Management    │
    └────────┬─────────────────┘
             ↓
    ┌──────────────────────────┐
    │ Content Extraction       │
    │ ├─ CSS Selector          │
    │ ├─ XPath                 │
    │ └─ Auto-discovery        │
    └────────┬─────────────────┘
             ↓
    ┌──────────────────────────┐
    │ LLM Validation (Groq)    │
    │ ├─ Structured Extraction │
    │ ├─ JSON Generation       │
    │ └─ Error Correction      │
    └────────┬─────────────────┘
             ↓
    ┌──────────────────────────┐
    │ Deduplication            │
    │ ├─ URL Matching          │
    │ ├─ DOI Matching          │
    │ ├─ Embedding Similarity  │
    │ └─ Fuzzy Name Matching   │
    └────────┬─────────────────┘
             ↓
    ┌──────────────────────────┐
    │ Enrichment Pipeline      │
    │ ├─ Metadata Extraction   │
    │ ├─ Classification        │
    │ ├─ Entity Linking        │
    │ └─ Date Normalization    │
    └────────┬─────────────────┘
             ↓
    ┌──────────────────────────┐
    │ Database Storage         │
    │ (PostgreSQL + Vectors)   │
    └──────────────────────────┘
```

### Scraping Categories

| Category | Purpose | Sources | Frequency |
|----------|---------|---------|-----------|
| **Events** | Conferences, workshops, CFP | EDAS, WikiCFP, conference websites | Daily |
| **Courses** | Training & education | Udemy, Coursera, institutional LMS | Weekly |
| **Tools** | NLP software & libraries | GitHub, PyPI, project sites | Continuous |
| **Institutions** | Universities & research centers | Institutional websites, directories | Monthly |
| **News** | Articles & announcements | News feeds, RSS, blogs | Hourly |

### Scraper Components

**HTML Scrapers:**
- `base_http_scraper.py` - HTTP-based extraction
- `selector_discovery.py` - Auto-detect CSS selectors
- `base_text.py` - Text content extraction
- `base_media.py` - Image/media handling

**Advanced Scrapers:**
- `playwright_scraper.py` - JavaScript-rendered sites
- `rss_scraper.py` - Feed aggregation
- `wayback_fallback.py` - Archive.org fallback
- `custom_scraper.py` - Extensible framework

**Specific Scrapers:**
- `confportal_scraper.py` - Conference portals
- `wikicfp_scraper.py` - WikiCFP scraping
- `courses.py` - Course platform scraping
- `tools.py` - NLP tools catalog
- `events.py` - Event calendar scraping
- `institutions.py` - Institution data
- `feed.py` - RSS/Feed scraping
- `news.py` - News article scraping

### Processing & Quality

**Deduplication:**
- URL matching
- DOI matching
- ArXiv ID matching
- Embedding-based similarity (768-dim)
- Fuzzy name matching

**Enrichment:**
- Metadata extraction
- Category classification
- Institution entity linking
- Author identification
- Date normalization
- Source attribution

**Validation:**
- LLM-powered (Groq llama-3.3-70b)
- JSON structure validation
- Field format checking
- Error correction
- Confidence scoring

**Resilience:**
- Retry logic (3 attempts, 0.6x backoff)
- Circuit breaker (fail-safe)
- Health monitoring
- Fallback to Wayback Machine
- Dead letter queue for failures
- Checkpoint-based resumption

### Configuration

```ini
GROQ_SCRAPING_API_KEY              # LLM API key
GROQ_SCRAPING_MODEL                # llama-3.3-70b-versatile
GROQ_SCRAPING_TIMEOUT              # 30 seconds
GROQ_SCRAPING_MAX_RETRIES          # 2 JSON parse retries

SCRAPING_CONNECT_TIMEOUT           # 3.0 seconds
SCRAPING_READ_TIMEOUT              # 7.0 seconds
SCRAPING_TOTAL_TIMEOUT             # 10.0 seconds
SCRAPING_LLM_TIMEOUT               # 30 seconds
SCRAPING_HEAD_TIMEOUT              # 10 seconds
SCRAPING_PLAYWRIGHT_TIMEOUT_MS     # 30000 milliseconds

SCRAPING_MAX_PAGES_HARD_LIMIT      # Max pagination pages
SCRAPING_WAYBACK_MAX_AGE_DAYS      # 90 days
SCRAPING_SOURCE_TEST_TTL_SECONDS   # 1800 seconds
SCRAPING_GLOBAL_FALLBACK_PROXY     # Optional proxy
```

### Logging & Monitoring

- **Format:** JSON-structured logs
- **Output:** `logs/scraping.log`
- **Metrics Tracked:**
  - Items scraped
  - Success/failure rates
  - Processing times
  - Deduplication efficiency
  - Enrichment accuracy
  - Source health scores
  - LLM validation confidence

---

## 🤖 COMPLETE AI/CHATBOT SERVICE

**Module:** `fastapi_chatbot/` **Status:** Production Grade

### Architecture

```
User Query
    ↓
┌──────────────────────────┐
│ Contextual Processing   │
│ ├─ Query Rewriting      │
│ ├─ Language Detection   │
│ └─ History Integration  │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ Intent Classification    │
│ (LLM-first routing)      │
├─ Platform help          │
├─ NLP concepts           │
├─ Resource search        │
├─ PDF analysis           │
└─ Web search             │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ Multi-Source Retrieval   │
│                          │
├─ Platform Docs          │ (Features, troubleshooting)
├─ NLP Knowledge Base     │ (Concepts, terminology)
├─ Research Resources     │ (Papers, datasets, tools)
├─ User Documents         │ (Uploaded PDFs)
└─ Web Search (Policy)    │ (Exa, Tavily)
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ Hybrid Retrieval         │
│ ├─ Vector similarity     │
│ ├─ BM25 keyword search   │
│ ├─ Semantic fusion       │
│ ├─ Deduplication         │
│ └─ Reranking             │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ Context Assembly         │
│ ├─ Top results (5)       │
│ ├─ Similarity threshold  │
│ ├─ Source attribution    │
│ └─ Confidence scoring    │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ LLM Answer Generation    │
│ (Groq llama-3.3-70b)    │
│ ├─ Prompt engineering    │
│ ├─ Token limits          │
│ └─ Temperature control   │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ Faithfulness Check       │
│ (Hallucination prevent)  │
│ ├─ Fact verification     │
│ ├─ Source grounding      │
│ └─ Confidence check      │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ Response Delivery        │
├─ Answer text            │
├─ Source attribution      │
├─ Confidence score        │
└─ Session persistence     │
└──────────────────────────┘
```

### Knowledge Sources

**1. Platform Documentation**
- Getting started guides
- Feature tutorials
- Navigation help
- API documentation
- Troubleshooting guides

**2. NLP Knowledge Base**
- Arabic NLP concepts
- Linguistic terminology
- NLP algorithms
- Research methodologies
- Best practices

**3. Research Resources**
- Academic papers
- Datasets & corpora
- Tools & software
- Educational materials
- Conference proceedings

**4. User Documents**
- Uploaded PDFs
- User files
- Session-scoped
- Owner-restricted

**5. Web Search**
- Exa.ai integration
- Tavily integration
- Policy-dependent
- Optional/configurable

### Conversation Features

- **Multi-turn Conversations:** Context retention
- **Session Management:** Persistent chat history
- **PDF Analysis:** Upload & ask about documents
- **Quick Queries:** No-context requests
- **Intent Routing:** Smart query classification
- **Language Support:** Arabic, English, French
- **Rate Limiting:** 30 req/minute per user
- **Session Timeout:** Configurable

### API Endpoints

```
POST /chat                 - Multi-turn conversation
POST /query                - Quick question
POST /ask                  - PDF-based question
POST /upload_pdf           - Document upload
POST /sessions             - List sessions
POST /sessions/rename      - Rename session
GET  /documents            - List user documents
POST /web_search           - Web search query
POST /search/platform      - Platform search
GET  /health               - Service health
```

### Models & Configuration

- **LLM Provider:** Groq API
- **User-facing Model:** llama-3.3-70b-versatile
- **Internal Model:** llama-3.1-8b-instant
- **Embeddings:** BAAI/bge-m3 (1024 dimensions)
- **Vector DB:** Qdrant with IVFFLAT indices
- **Top-K Retrieval:** Default 5
- **Similarity Threshold:** Default 0.7
- **Response Timeout:** 30 seconds

---

## 🔐 SECURITY & AUTHENTICATION

### Authentication Methods

1. **Email-based Auth:**
   - Email + password login
   - Email verification (6-digit code)
   - Password reset flow
   - Session management

2. **Two-Factor Authentication:**
   - OTP via email
   - Time-limited codes (5 min)
   - Mandatory on signup/login
   - Redis-backed storage

3. **Social Login (via Allauth):**
   - Google OAuth
   - Facebook OAuth
   - Other providers (configurable)

### Authorization & Access Control

1. **Role-Based Access (RBAC):**
   - User roles: User, Staff, Admin
   - Permission-based decorators
   - Group-based permissions

2. **Object-Level Permissions:**
   - Creator write access
   - Team member permissions
   - Institution admin permissions
   - Public/private visibility

3. **Feature Flags:**
   - Configurable via admin
   - Per-user feature access
   - Institutional settings
   - Beta feature testing

### Data Protection

1. **Blocking System:**
   - User blocking
   - Content hiding from blocked users
   - Bidirectional enforcement
   - Friendship model tracking

2. **Session Isolation:**
   - User-specific sessions
   - Document scoping
   - Project-based isolation
   - Institution-level separation

3. **Rate Limiting:**
   - Per-user limits
   - Per-IP limits
   - Chatbot: 30 req/minute
   - Login: Rate limited failures
   - Search: Per-user quotas

### Infrastructure Security

1. **HTTPS/TLS:**
   - SSL certificates
   - Nginx termination
   - Secure cookies
   - HSTS headers

2. **CSRF Protection:**
   - Django CSRF tokens
   - POST request validation
   - Cookie-based tokens

3. **File Upload Security:**
   - Size validation
   - Type validation
   - Virus scanning
   - Secure storage paths
   - CDN delivery

4. **API Security:**
   - Token authentication
   - Rate limiting
   - Input validation
   - Output sanitization

---

## 📊 DATABASE SCHEMA OVERVIEW

### Core Tables (30+)

**User Management:**
- `accounts_customuser` - User profiles, authentication
- `accounts_friendship` - User relationships, blocking
- `accounts_experience` - Work/education history
- `accounts_twofactorauth` - 2FA configuration

**Resources:**
- `resources_resourcebase` - Abstract base
- `resources_document` - Research papers
- `resources_corpus` - Datasets
- `resources_nlptool` - NLP tools
- `resources_course` - Educational courses

**Projects:**
- `projects_project` - Project metadata
- `projects_projectmember` - Team memberships

**Community:**
- `forum_topic` - Discussion threads
- `feed_question` - Q&A questions
- `feed_answer` - Q&A answers
- `feed_post` - News/blog posts
- `direct_messages_message` - Private messages

**Events & Collaboration:**
- `events_event` - Conferences, workshops
- `project_chatroom_projectchat` - Team chat
- `project_chatroom_projectchatmessage` - Messages
- `sharing_share` - Content shares
- `sharing_sharereply` - Share discussions

**Notifications & Settings:**
- `notifications_notification` - Alert system
- `feed_activity` - Activity stream
- `settings_globalsettings` - Platform config

**Scraping:**
- `scraping_scrapingsource` - What to scrape
- `scraping_scrapedresult` - Scraped content
- `scraping_scrapingcheckpoint` - Progress
- `scraping_sourcehealth` - Reliability

**Chatbot:**
- `chatbot_chatsession` - Chat sessions
- `chatbot_chatmessage` - Chat history

**Taxonomy:**
- `taxonomy_researchdomain` - Domain hierarchy
- `taxonomy_nlpmethod` - NLP methods
- `taxonomy_dataset` - Dataset tracking

---

## 🌍 Internationalization (i18n)

### Languages Supported

| Language | Code | Status | RTL |
|----------|------|--------|-----|
| Arabic | ar | Full | ✅ |
| English | en | Full | ❌ |
| French | fr | Full | ❌ |
| Spanish | es | Limited | ❌ |

### Localization Features

1. **Content Translation:**
   - Bilingual titles
   - Bilingual descriptions
   - Bilingual names
   - Bilingual bios

2. **UI Translation:**
   - Message translation files (.po)
   - Template translation tags
   - JavaScript translation
   - Email templates

3. **Date/Time Localization:**
   - Language-specific formatting
   - Timezone handling
   - Calendar support (Islamic/Gregorian)

4. **RTL Support:**
   - Arabic-specific styling
   - Direction detection
   - Bidirectional text handling

---

## 📈 Performance & Optimization

### Caching Strategy

1. **Redis Cache:**
   - Session data
   - Rate limit counters
   - OTP storage
   - Query result caching

2. **Database Optimization:**
   - Query optimization
   - Select_related/prefetch_related
   - Database indexing
   - Connection pooling

3. **Frontend Optimization:**
   - Static file caching
   - Lazy loading
   - Image optimization
   - CSS/JS bundling

### Async Processing

1. **Celery Tasks:**
   - Document ingestion
   - Embedding generation
   - Web scraping
   - Email sending
   - Notification delivery
   - Search indexing

2. **Background Jobs:**
   - Periodic tasks (Celery Beat)
   - Scheduled scraping
   - Health monitoring
   - Cache warming

---

## 🛠️ DEVELOPMENT & DEPLOYMENT

### Local Development

```bash
# Setup
python -m venv env
source env/bin/activate
pip install -r requirements.txt

# Database
python manage.py migrate

# Run servers
python manage.py runserver              # Django (8000)
cd fastapi_chatbot && uvicorn app.main:app --reload  # FastAPI (8001)
celery -A Plateforme worker -l info    # Celery worker
```

### Docker Deployment

```bash
docker-compose up -d
```

Services:
- Django (Gunicorn, port 8000)
- FastAPI (Uvicorn, port 8001)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Elasticsearch (port 9200)
- Qdrant (port 6333)
- Prometheus (port 9090)
- Grafana (port 3000)
- Nginx (port 80/443)

---

## 📊 Platform Statistics

### Feature Count
- **15+ Django Apps**
- **30+ Database Models**
- **8 Elasticsearch Document Types**
- **25+ Notification Types**
- **6 Resource Types**
- **5 Scraper Categories**
- **4 Conversation Modes**
- **18+ AI Specializations**
- **4+ Languages**

### Database Scope
- **1000+ Dimensional** vectors
- **768-Dimensional** embeddings (BM25 + semantic)
- **IVFFLAT** vector indexing
- **PostgreSQL** relational data
- **Redis** caching & sessions
- **Qdrant** vector persistence

### Performance Targets
- API Response: <500ms (p95)
- Chatbot Response: 1-3s
- Search Query: <200ms
- Page Load: <2s

---

## 🎯 CONCLUSION

**Plateforme_NLP** is a comprehensive, production-ready Arabic NLP research platform combining:

✅ **Advanced AI/ML** - RAG chatbot, vector search, embeddings  
✅ **Rich Resource Library** - 6 content types, full-text search  
✅ **Collaborative Tools** - Projects, teams, chat, forums  
✅ **Enterprise Security** - 2FA, blocking, RBAC, encryption  
✅ **Automated Harvesting** - Web scraping, enrichment, dedup  
✅ **Global Scale** - Multilingual, monitoring, optimization  
✅ **Community Focus** - Events, notifications, sharing, Q&A  

### Platform Serves:
- 👨‍🔬 **Researchers** - Discover resources, collaborate
- 🎓 **Academics** - Manage courses, projects
- 🏛️ **Institutions** - Showcase research, track output
- 💼 **Professionals** - Network, learn, contribute
- 🌍 **Global Community** - Arabic NLP knowledge hub

**This is a complete, professional, production-grade research platform.**

---

**Last Updated:** April 10, 2026  
**Status:** ✅ Production Ready  
**Version:** 2.0+ (Continuous Development)  
**Report Completeness:** 100% - COMPREHENSIVE

