# 🕷️ Web Scraping Module — NLP Platform

## Table of Contents

1. [What is Web Scraping?](#what-is-web-scraping)
2. [Module Overview](#module-overview)
3. [Architecture](#architecture)
4. [Scrapers in Detail](#scrapers-in-detail)
5. [Data Sources](#data-sources)
6. [Models & Database](#models--database)
7. [Admin Panel Integration](#admin-panel-integration)
8. [Running Scrapers](#running-scrapers)
9. [How Each Scraper Works](#how-each-scraper-works)
10. [Safety & Data Quality](#safety--data-quality)
11. [Configuration & Customisation](#configuration--customisation)
12. [Troubleshooting](#troubleshooting)
13. [File Structure](#file-structure)

---

## What is Web Scraping?

**Web scraping** is the automated process of extracting data from websites and online APIs. Instead of manually copying information, a scraper program sends HTTP requests to web pages or APIs, parses the returned content (HTML, JSON, XML), and extracts structured data.

In the context of this NLP platform, web scraping is used to **automatically discover and import** academic resources related to Natural Language Processing (NLP) — including conferences, tools, research papers, courses, and institutions — from credible sources on the internet.

### How It Works (Simplified)

```
1. Scraper sends HTTP request  →  Target API / Website
2. Target responds with data   →  JSON / XML / HTML
3. Scraper parses the response →  Extracts structured fields
4. Data is validated           →  Duplicate check, field validation
5. Records created in database →  Django model instances (pending approval)
```

### Why Not Just Manual Entry?

| Manual Entry | Web Scraping |
|---|---|
| Time-consuming | Automated in seconds |
| Limited by human effort | Can process hundreds of records |
| May miss updates | Can be re-run to catch new data |
| Prone to typos | Consistent, structured data |
| Doesn't scale | Easily expandable with new sources |

---

## Module Overview

The scraping module is a standalone Django app (`scraping/`) that provides:

- **5 specialised scrapers** — one for each resource category (Events, Tools, News, Courses, Institutions)
- **Admin-only access** — only platform administrators can trigger scrapers
- **Professional dashboard** — a tabbed interface inside the admin panel with real-time feedback
- **Run logging** — every scraping execution is recorded with status, item counts, and errors
- **Duplicate detection** — scrapers check for existing records before creating new ones
- **Elasticsearch safety** — ES indexing is temporarily disabled during scraping to prevent signal crashes
- **Pending approval workflow** — all scraped items are created with `approval_status='pending'` so admins can review them

### What Gets Scraped

| Category | Target Model | Sources | Typical Yield |
|---|---|---|---|
| **Events** | `events.Event` | WikiCFP + ConferenceAlerts (Algeria, Morocco, Tunisia, Egypt) + AllConferenceAlert Algeria + 22 curated Arabic/MENA events | ~30 events |
| **Tools** | `resources.NLPTool` | HuggingFace Hub API (14 queries) + 10 curated LLMs/speech models + 7 Arabic datasets | ~70 tools |
| **News** | `QA.Post` | arXiv API + Semantic Scholar (with retry/backoff) | ~20 papers |
| **Courses** | `resources.Course` | MIT OCW + Coursera (7 NLP courses) + YouTube (7 playlists) + 10 curated | ~34 courses |
| **Institutions** | `institutions.Institution` | ROR + OpenAlex + 10 Algerian + 10 African/Arabic labs + 10 North African + 10 Arabic/Gulf | ~108 institutions |

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────┐
│                  Admin Panel                     │
│  ┌─────────────────────────────────────────────┐ │
│  │        Scraping Dashboard (AJAX)            │ │
│  │  [Events] [Tools] [News] [Courses] [Inst.] │ │
│  │        ▼ Click "Run Scraper"                │ │
│  └─────────────────────────────────────────────┘ │
│           │ POST /scraping/run/<category>/       │
│           ▼                                      │
│  ┌─────────────────────────────────────────────┐ │
│  │           views.py → run_scraper()          │ │
│  │  1. Create ScrapingRun (status=running)     │ │
│  │  2. Get scraper instance from registry      │ │
│  │  3. Call scraper.run()                      │ │
│  │  4. Update ScrapingRun (status=completed)   │ │
│  │  5. Return JSON response                    │ │
│  └─────────────────────────────────────────────┘ │
│           │                                      │
│           ▼                                      │
│  ┌─────────────────────────────────────────────┐ │
│  │          BaseScraper.run()                  │ │
│  │  • Disable ES indexing (monkey-patch)       │ │
│  │  • Call self.scrape() (abstract)            │ │
│  │  • Re-enable ES indexing                    │ │
│  │  • Return summary dict                     │ │
│  └─────────────────────────────────────────────┘ │
│           │                                      │
│           ▼                                      │
│  ┌──────────────────────────────────────┐        │
│  │ Concrete Scraper (e.g. EventScraper) │        │
│  │  • HTTP requests to external APIs    │        │
│  │  • Parse responses                   │        │
│  │  • Create Django model instances     │        │
│  │  • Track created/skipped counts      │        │
│  └──────────────────────────────────────┘        │
│           │                                      │
│           ▼                                      │
│  ┌──────────────────────────────────────┐        │
│  │     PostgreSQL Database               │        │
│  │  Event, NLPTool, Course, Post,       │        │
│  │  Institution, ScrapingRun tables     │        │
│  └──────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

---

## Running the Evaluation Suite

The evaluation harness validates extraction quality with offline fixtures and computes key quality metrics.

### What It Covers

- Precision and recall per category (`news`, `events`, `courses`, `institutions`, `tools`)
- Date parsing accuracy checks for date-bearing categories
- Duplicate detection effectiveness
- LLM relevance false-positive-rate checks with deterministic test doubles
- Automatic markdown report generation under `reports/`

### Fixture Locations

- Ground truth JSON: `Plateforme/tests/scraping/fixtures/ground_truth/`
- Raw HTML snapshots: `Plateforme/tests/scraping/fixtures/raw_html/`

### Run Commands

From workspace root:

```bash
make eval
```

Equivalent direct pytest command:

```bash
pytest Plateforme/tests/scraping -v
```

### Report Output

The suite writes a timestamped markdown report file:

- `reports/scraping_eval_<YYYYMMDD_HHMMSS>.md`

Each report includes global micro metrics and per-category precision/recall/date-accuracy tables.

### Key Design Decisions

1. **Abstract Base Class (`BaseScraper`)** — All scrapers inherit from a common base that provides HTTP session management, date parsing, system user creation, country/institution helpers, and ES signal safety.

2. **Registry Pattern** — Scrapers are registered in `scrapers/__init__.py` via a `SCRAPERS` dictionary. The view layer looks up scrapers by category key, making it easy to add new scrapers.

3. **Synchronous Execution** — Scrapers run synchronously within the Django request. Since they typically complete in 5–30 seconds, there's no need for Celery task queues.

4. **Curated Fallback Data** — Events and Courses scrapers include hardcoded lists of well-known NLP conferences and courses. This ensures meaningful data even when external APIs are unavailable.

5. **ES Signal Monkey-Patching** — The platform uses `django-elasticsearch-dsl` which triggers indexing on every `post_save`. During scraping (which creates many records), this is temporarily disabled to prevent performance issues and potential crashes.

---

## Scrapers in Detail

### 1. Events Scraper (`scrapers/events.py`)

**What it does:** Discovers NLP conferences, workshops, and events.

**Sources:**
- **WikiCFP** (wikicfp.com) — Scrapes the Call For Papers website for NLP-related events by searching for keywords ("natural language processing", "NLP", "computational linguistics"). Parses HTML tables using BeautifulSoup.
- **ConferenceAlerts Algeria** (conferencealerts.co.in/algeria) — Scrapes upcoming academic conferences in Algeria. Extracts title, dates, city, and links from cards/lists.
- **AllConferenceAlert Algeria** (allconferencealert.com/algeria.html) — Alternative Algerian conference source. Parses table rows for title, date, city, and category.
- **Curated List** — 12 major NLP conferences manually maintained in the source code (ACL, EMNLP, NAACL, COLING, EACL, AAAI, IJCNLP-AACL, ArabicNLP, LREC-COLING, SIGIR, NeurIPS, WANLP).

**How it works:**
1. Tries WikiCFP search with 3 different queries
2. Scrapes ConferenceAlerts Algeria and AllConferenceAlert Algeria for regional events
3. Parses HTML rows (2 rows per event: title + dates/location)
4. Falls back to curated event list
5. For each event, resolves the organising institution (creates if needed)
6. Creates `events.Event` with all fields filled (title, description, dates, location, organizer, etc.)

**Target Model Fields (`events.Event`):**
- `title` / `title_en` / `title_ar` — Event name in both languages
- `description` / `description_en` / `description_ar` — Full description
- `event_type` — conference, workshop, seminar, etc.
- `domains` — NLP sub-domains (comma-separated)
- `location` / `location_en` / `location_ar` — Venue city+country
- `start_date`, `end_date`, `submission_deadline` — Key dates
- `website` — Official event URL
- `contact_email` — Contact address
- `organizer` — FK to `institutions.Institution`
- `created_by` — FK to the system scraper user
- `approval_status` — Set to `"pending"`

### 2. Tools Scraper (`scrapers/tools.py`)

**What it does:** Discovers NLP tools and models from the HuggingFace Hub.

**Sources:**
- **HuggingFace Hub API** (`huggingface.co/api/models`) — A REST API that returns metadata for machine learning models. Searched with 14 queries focused on Arabic NLP, LLMs, and speech models.
- **Curated Arabic LLMs** — 10 handpicked Arabic/multilingual LLMs and NLP toolkits including Jais (13B/30B), AceGPT, ALLaM, Whisper Arabic, MMS, CAMeL Tools, FARASA, Stanza Arabic, and AraBERT v2.
- **Curated Arabic Datasets** — 7 HuggingFace datasets for Arabic NLP: Arabic Speech Corpus, HARD (sentiment), ARCD (QA), LABR (reviews), WikiANN-Arabic (NER), Calliar (Algerian dialect), NADI (dialect identification).

**How it works:**
1. Sends 14 separate API queries (arabic nlp, camelbert, arabert, arabic speech recognition, jais arabic, arabic llm, etc.)
2. Deduplicates by model ID across queries
3. Maps HuggingFace pipeline tags to platform tool types (e.g., `text-classification` → `sentiment_analysis`)
4. Maps language tags (ar, en, fr, es) to platform language codes
5. Imports curated LLM tools and speech models with detailed descriptions
6. Imports curated Arabic datasets as NLPTool entries prefixed with `[Dataset]`
7. Creates `resources.NLPTool` with model details, download counts, tags, and link

**Target Model Fields (`resources.NLPTool`):**
- `title` / `title_en` / `title_ar` — Human-readable model name
- `description` / `description_en` / `description_ar` — Model details (author, pipeline, downloads, tags)
- `tool_type` — Mapped from pipeline tag  
- `version` — Set to `"latest"`
- `access_link` — HuggingFace model page URL
- `documentation_link` — Same as access link
- `supported_languages` — Primary language code
- `language` — Content language
- `keywords` — From model tags

### 3. News Scraper (`scrapers/news.py`)

**What it does:** Discovers recent NLP research papers from academic databases.

**Sources:**
- **arXiv API** (`export.arxiv.org/api/query`) — Queries the cs.CL (Computation & Language) category for recent papers about Arabic/NLP/language models. Returns Atom XML.
- **Semantic Scholar API** (`api.semanticscholar.org`) — Searches for Arabic NLP papers from 2024–2025. Returns JSON.

**How it works:**
1. Queries arXiv for 20 most recent cs.CL papers matching Arabic/NLP keywords
2. Parses Atom XML to extract title, authors, abstract, links, categories
3. Queries Semantic Scholar for 15 Arabic NLP papers
4. For each paper, creates a `QA.Post` (the platform's news model) with:
   - Rich markdown content (authors, abstract, links to full paper/PDF)
   - Unique slug generated from title

**Target Model Fields (`QA.Post`):**
- `title` / `title_en` / `title_ar` — Paper title
- `content` / `content_en` / `content_ar` — Markdown body with authors, abstract, links
- `slug` — URL-safe unique identifier
- `author` — FK to system scraper user
- `approval_status` — Set to `"pending"`

### 4. Courses Scraper (`scrapers/courses.py`)

**What it does:** Discovers NLP courses from universities.

**Sources:**
- **MIT OpenCourseWare API** (`ocw.mit.edu/api/v0/search/`) — Searches for NLP-related courses. May return 404 if API is deprecated.
- **Coursera** — 7 curated NLP courses: NLP Specialization (DeepLearning.AI), ML with Python (IBM), Deep Learning Specialization (Andrew Ng), Intro to LLMs (Google Cloud), Applied Text Mining (U Michigan), Prompt Engineering (Vanderbilt), Arabic for Beginners (Al-Azhar).
- **YouTube Playlists** — 7 curated NLP video playlists: Arabic NLP Full Course, Stanford CS224N, HuggingFace NLP Course, NLP Zero to Hero (Arabic subtitles), ML in Arabic (Hesham Asem), CMU CS 11-747, Arabic AI and Deep Learning.
- **Curated List** — 10 well-known NLP courses from top universities (Stanford CS224N, CMU CS11-711, MIT 6.8610, McGill COMP 550, Oxford DL-NLP, NYU Abu Dhabi Arabic NLP, HuggingFace Course, Stanford SLP, ETH Multilingual NLP, UIUC Text Mining).

**How it works:**
1. Tries MIT OCW API search
2. Imports Coursera NLP courses (creates institution per course provider)
3. Imports YouTube NLP playlists (creates "YouTube Educational Content" institution)
4. Imports curated university courses with full syllabi
5. For each course, resolves/creates the university institution
6. Creates `resources.Course` with all academic details

**Target Model Fields (`resources.Course`):**
- `title` / `title_en` / `title_ar` — Course name
- `description` / `description_en` / `description_ar` — Course overview
- `field` — NLP sub-field (nlp, ml, text_mining, etc.)
- `academic_level` — bachelor / master
- `teacher` — FK to system user
- `institution` — FK to `institutions.Institution`
- `academic_year` — Auto-generated (e.g., "2025-2026")
- `access_link` — Course website
- `language` — Content language
- `keywords` — NLP-related keywords
- `prerequisites` — Required background
- `syllabus` — Week-by-week topics

### 5. Institutions Scraper (`scrapers/institutions.py`)

**What it does:** Discovers universities and research centres active in NLP.

**Sources:**
- **ROR API v2** (`api.ror.org/organizations`) — The Research Organization Registry, a community-led registry of research organisations. Searched with 4 queries. Uses v2 format (names/locations/links arrays).
- **OpenAlex API** (`api.openalex.org/institutions`) — Open scholarly metadata. Searched for institutions with NLP/Arabic research output.
- **Algerian Universities** — 10 curated Algerian institutions: USTHB, University of Algiers 1, University of Oran 1, University of Constantine 1, ESI, University of Tlemcen, University of Béjaïa, University of Batna 2, University of Blida 1, and CERIST (research centre).
- **African & Arabic NLP Labs** — 10 curated research labs and institutions: Masakhane NLP (South Africa), InstaDeep (Tunisia), Cairo University FCAI (Egypt), KACST (Saudi Arabia), AIMS (Rwanda), UCT NLP Group (South Africa), UM6P (Morocco), QCRI (Qatar), NYU Abu Dhabi CAMeL Lab (UAE), KAUST (Saudi Arabia).

**How it works:**
1. Queries ROR with 4 keywords, deduplicates by ROR ID
2. Parses v2 format: extracts display name from `names[]`, location from `locations[].geonames_details`, website from `links[]`
3. Queries OpenAlex for 15 institutions
4. Imports 10 curated Algerian universities with bilingual fields (Arabic/English)
5. Imports 10 curated African and Arabic NLP laboratories
6. Parses geo data, works count, and citations count
7. Creates `institutions.Institution` with detailed descriptions

**Target Model Fields (`institutions.Institution`):**
- `name` / `name_en` / `name_ar` — Institution name
- `acronym` — Short form (e.g., "MIT")
- `type` — University, Research Center, Other
- `country` — FK to `institutions.Country`
- `city` / `city_en` / `city_ar` — City name
- `website` — Official URL
- `email` — Contact email
- `phone` — Contact phone
- `address` / `address_en` / `address_ar` — Physical address
- `description` / `description_en` / `description_ar` — Institution overview
- `created_by` — FK to system scraper user

---

## Models & Database

The scraping app defines four models in `scraping/models.py`:

### ScrapingSource

Configurable source definition (currently populated via admin):

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | CharField | Source name |
| `category` | CharField | events / tools / news / courses / institutions |
| `base_url` | URLField | Source URL |
| `description` | TextField | Source description |
| `is_active` | BooleanField | Whether source is enabled |
| `last_scraped` | DateTimeField | Last successful scrape |
| `created_at` | DateTimeField | Auto-set on creation |

### ScrapingRun

Log of each scraping execution:

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `category` | CharField | Which scraper was run |
| `status` | CharField | running / completed / failed |
| `items_found` | PositiveIntegerField | Total items discovered |
| `items_created` | PositiveIntegerField | New items created in DB |
| `items_skipped` | PositiveIntegerField | Items skipped (duplicates) |
| `errors` | TextField | Error messages (newline-separated) |
| `started_at` | DateTimeField | When the run started |
| `completed_at` | DateTimeField | When the run finished |
| `triggered_by` | ForeignKey(User) | Admin who triggered it |
| `duration` | Property | Computed from started_at/completed_at |

### ScrapingSourceHealth

Per-source health tracking with circuit breaker state (Phase 5):

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `category` | CharField | Scraper category |
| `source_name` | CharField | Logical source name (e.g. "WikiCFP") |
| `base_url` | URLField | Source base URL |
| `total_attempts` | PositiveIntegerField | Lifetime request count |
| `total_successes` | PositiveIntegerField | Successful requests |
| `total_failures` | PositiveIntegerField | Failed requests |
| `consecutive_failures` | PositiveIntegerField | Current failure streak |
| `health_score` | FloatField | 0–100, decays on failure, recovers on success |
| `circuit_state` | CharField | closed / open / half_open |
| `circuit_opened_at` | DateTimeField | When circuit was tripped |
| `circuit_cooldown_seconds` | PositiveIntegerField | Seconds before half-open probe |
| `last_attempt_at` | DateTimeField | Most recent request time |
| `last_success_at` | DateTimeField | Most recent success |
| `last_failure_at` | DateTimeField | Most recent failure |
| `avg_response_time` | FloatField | Exponential moving average (seconds) |
| `last_error` | TextField | Most recent error message |

### ScrapedItemMeta

Per-item intelligence metadata created by the scoring pipeline (Phase 6):

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `category` | CharField | events / tools / news / courses / institutions |
| `item_title` | CharField(300) | Title of the scored item |
| `item_id` | UUIDField | Optional FK reference to the original model record |
| `domain_scores` | JSONField | Dict of domain → confidence (e.g. `{"arabic_nlp": 0.6}`) |
| `primary_domain` | CharField | Best-matching domain or `"general"` |
| `relevance_score` | FloatField | 0–100 composite score |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-updated |

Indexed on `(category, primary_domain)` and `-relevance_score`.

---

## Admin Panel Integration

The scraping dashboard is accessible **only to administrators** through the admin panel sidebar.

### Access Control

- Views are protected with `@login_required` + `@user_passes_test(is_admin)` decorators
- `is_admin` checks `user.is_staff or user.is_superuser`
- The scraping link appears in the admin sidebar (in `base_admin.html`), not in the main user sidebar

### Template Inheritance

```
base_admin.html
    └── scraping/dashboard.html
```

The dashboard extends `base_admin.html` and renders inside the admin panel layout with the standard admin sidebar navigation.

### URL Routing

```
/<lang>/scraping/                → scraping:dashboard   (GET)
/<lang>/scraping/run/<category>/ → scraping:run_scraper  (POST, AJAX)
```

URLs are defined in `scraping/urls.py` and included in the main URL configuration under `i18n_patterns`.

---

## Running Scrapers

### Method 1: Admin Dashboard (Recommended)

1. Log in as an admin user
2. Navigate to the **Admin Panel** from the sidebar
3. Click **Web Scraping** in the admin sidebar
4. Select a category tab (Events, Tools, News, Courses, Institutions)
5. Click **"Run Scraper"**
6. Watch real-time progress (loading spinner → summary + results table)

### Method 2: Management Command (CLI)

```bash
# Run a specific scraper
python manage.py run_scraper --category events
python manage.py run_scraper --category tools
python manage.py run_scraper --category news
python manage.py run_scraper --category courses
python manage.py run_scraper --category institutions

# Run ALL scrapers sequentially
python manage.py run_scraper --all
```

### Method 3: Inside Docker

```bash
docker compose exec web python manage.py run_scraper --all
docker compose exec web python manage.py run_scraper --category events
```

---

## How Each Scraper Works

### Execution Flow (All Scrapers)

```python
scraper = get_scraper("events")  # From registry
result = scraper.run()           # Returns summary dict
```

Inside `run()`:
1. **Disable ES indexing** — `_disable_es_indexing()` monkey-patches the ES registry
2. **Call `scrape()`** — The abstract method implemented by each scraper
3. **Re-enable ES indexing** — `_enable_es_indexing()` restores original methods
4. **Return summary** — `{"items_created": N, "items_skipped": N, "errors": [...], "results": [...]}`

### System User

All scraped items are attributed to a **system user** (`system@nlp-platform.local`). This user:
- Is created automatically on first scraper run
- Has an unusable password (cannot log in)
- Is created via `bulk_create()` to avoid triggering ES `post_save` signals
- Is cached in `self._system_user` for the duration of a scraping run

### Duplicate Detection

Each scraper checks for existing records before creating new ones:
- **Events**: Checks `title_en__iexact` and `website` uniqueness
- **Tools**: Checks `access_link` and `title_en__iexact` uniqueness
- **News**: Checks `title_en__iexact` and `slug` uniqueness
- **Courses**: Checks `title_en__iexact` uniqueness
- **Institutions**: Checks `name_en__iexact` uniqueness

This means running a scraper multiple times is safe — it will only create new items.

### Country & Institution Auto-Creation

The base scraper provides helpers:
- `get_or_create_country(name_en, code)` — Creates a `Country` if it doesn't exist
- `get_or_create_institution(name, **kwargs)` — Creates an `Institution` (with country, city, website, etc.) if not found by `name_en__iexact`

These are used by Events (conference organisers) and Courses (universities).

---

## Safety & Data Quality

### Approval Workflow

All scraped items are created with `approval_status='pending'`. This means:
- They appear in the admin panel's pending approval queue
- They are **not visible** to regular users until an admin approves them
- Admins can review, edit, or reject items before they go live

### Rate Limiting & Politeness

- Each scraper uses a shared `requests.Session` with **rotating User-Agent** strings (5-agent pool)
- Default timeout is 30 seconds (configurable via `DEFAULT_TIMEOUT` class attribute)
- Transient failures (429, 5xx, connection errors, timeouts) trigger **automatic retry with exponential back-off**
- Base backoff is 2s, doubling per attempt, capped at 60s (configurable via `BACKOFF_BASE` / `BACKOFF_MAX`)
- Max retries default to 3 (configurable via `MAX_RETRIES`)
- The HuggingFace scraper limits to ~100 models across 14 queries
- The ROR and OpenAlex APIs are free and rate-limit-friendly
- arXiv requests respect the API's built-in pagination

### Circuit Breaker

Each external source is tracked by the `ScrapingSourceHealth` model. When a source fails repeatedly:

1. **Health score** starts at 100 and loses 15 points per failure / gains 10 per success
2. Circuit **trips open** when score drops below 25 *or* 3 consecutive failures occur
3. While open, all requests to that source are **skipped** (no wasted time)
4. After a cooldown period (default 300s), the circuit moves to **half-open** and allows one probe request
5. If the probe succeeds the circuit **closes**; if it fails, it **re-opens**

Admins can view source health in the Django admin under **Source Health Records**.

### Error Handling

- Individual item failures don't crash the entire scraper run
- **Structured errors** are collected in `self.structured_errors` with type, source, URL, timestamp, and extra metadata
- Legacy `self.errors` list is maintained for backward compatibility
- The `ScrapingRun` record tracks all errors
- Network failures are caught by `safe_request()` with per-attempt logging

### Elasticsearch Safety

- ES indexing is disabled during scraping via monkey-patching `registry.update` and `registry.delete`
- This prevents cascading `post_save` signal errors when creating many records
- Indexing is restored in a `finally` block to guarantee re-enablement

---

## Configuration & Customisation

### Adding a New Scraper

1. Create a new file in `scraping/scrapers/` (e.g., `datasets.py`)
2. Subclass `BaseScraper` and implement `scrape()`:

```python
from .base import BaseScraper

class DatasetScraper(BaseScraper):
    name = "NLP Datasets"
    category = "datasets"

    def scrape(self):
        # Your scraping logic here
        pass
```

3. Register it in `scraping/scrapers/__init__.py`:

```python
from .datasets import DatasetScraper

SCRAPERS = {
    # ... existing scrapers ...
    "datasets": DatasetScraper,
}

CATEGORY_META = {
    # ... existing meta ...
    "datasets": {
        "label": "Datasets",
        "icon": "fa-database",
        "color": "#f59e0b",
        "description": "Discover NLP datasets from the web.",
        "sources": ["HuggingFace Datasets", "Papers With Code"],
    },
}
```

4. Add the category to `ScrapingSource.CATEGORY_CHOICES` in `models.py`
5. Run `python manage.py makemigrations scraping && python manage.py migrate`

### Modifying Curated Data

- **Events**: Edit `CURATED_EVENTS` list in `scrapers/events.py`
- **Courses**: Edit `CURATED_COURSES`, `COURSERA_COURSES`, or `YOUTUBE_PLAYLISTS` lists in `scrapers/courses.py`
- **Tools**: Edit `CURATED_LLM_TOOLS` or `CURATED_DATASETS` lists in `scrapers/tools.py`
- **Institutions**: Edit `ALGERIAN_UNIVERSITIES` or `AFRICAN_NLP_LABS` lists in `scrapers/institutions.py`
- **Conference organisers**: Edit `CONFERENCE_ORGS` dict in `scrapers/events.py`

### Adjusting API Limits

- **HuggingFace**: Edit `QUERIES` list in `scrapers/tools.py` (change `limit` values)
- **arXiv**: Edit `max_results` in `news.py` `_scrape_arxiv()` params
- **ROR**: Results per query controlled by the API (default ~20)
- **OpenAlex**: Edit `per_page` in `institutions.py` `_scrape_openalex()` params

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|---|---|---|
| "beautifulsoup4 is not installed" | `bs4` not in container | `pip install beautifulsoup4 lxml` inside Docker |
| WikiCFP returns no results | Site may be down or blocking | Curated events still import; circuit breaker will skip future attempts |
| MIT OCW returns 404 | API endpoint deprecated | Curated courses still import |
| Semantic Scholar returns 429 | Rate limit exceeded | Scraper retries 5× with exponential backoff (30s–180s); arXiv data still works |
| "Circuit open for X — skipping" | Source failed too many times | Check Source Health in admin; health recovers after cooldown |
| "Scraper error: ..." | Network timeout or API change | Check structured error logs; scraper records partial results |
| Duplicate items not created | Working as intended | Scraper checks for existing records |
| Items not visible to users | Pending approval | Admin must approve items in the admin panel |

### Logs

Scraper logs are written to Django's logging system under the `scraping.scrapers` namespace:

```python
# In settings.py, you can add:
LOGGING = {
    'loggers': {
        'scraping': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

### Checking Scraping History

In the Django admin (`/admin/`), navigate to:
- **Scraping Sources** — View/edit source configurations
- **Scraping Runs** — View all past runs with status, counts, and errors
- **Source Health Records** — View per-source health scores, circuit breaker states, failure counts, and average response times

Or use the Web Scraping dashboard in the admin panel — each category tab shows its recent runs.

---

## File Structure

```
scraping/
├── __init__.py                  # Django app init
├── admin.py                     # Django admin registration (ScrapingSource, ScrapingRun, ScrapingSourceHealth, ScrapedItemMeta)
├── apps.py                      # Django app config
├── intelligence.py              # Intelligence module (keyword expansion, query gen, domain classification, scoring, trends)
├── models.py                    # ScrapingSource + ScrapingRun + ScrapingSourceHealth + ScrapedItemMeta models
├── urls.py                      # URL routing (dashboard + run endpoint)
├── views.py                     # Dashboard view + AJAX run_scraper endpoint
├── README.md                    # This documentation
│
├── scrapers/
│   ├── __init__.py              # Scraper registry (SCRAPERS dict, CATEGORY_META)
│   ├── base.py                  # BaseScraper abstract class (ES safety, retry/backoff, circuit breaker, UA rotation, intelligence)
│   ├── events.py                # EventScraper (WikiCFP + curated conferences + MENA events)
│   ├── tools.py                 # ToolScraper (HuggingFace Hub API)
│   ├── news.py                  # NewsScraper (arXiv + Semantic Scholar)
│   ├── courses.py               # CourseScraper (MIT OCW + curated courses)
│   └── institutions.py          # InstitutionScraper (ROR + OpenAlex + North African + Arabic institutions)
│
├── management/
│   └── commands/
│       └── run_scraper.py       # CLI: python manage.py run_scraper --category <cat>
│
├── migrations/
│   ├── 0001_initial.py          # Initial migration
│   ├── 0002_scrapingrun_task_id.py
│   ├── 0003_add_scraping_source_health.py  # ScrapingSourceHealth model
│   └── 0004_add_scraped_item_meta.py       # ScrapedItemMeta model (Phase 6)
│
└── templates/
    └── scraping/
        └── dashboard.html       # Professional admin dashboard (tabbed, AJAX, responsive)
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `requests` | (bundled with Django) | HTTP requests to APIs |
| `beautifulsoup4` | 4.12.3 | HTML parsing (WikiCFP) |
| `lxml` | 5.3.0 | Fast HTML/XML parser backend |
| `python-dateutil` | (bundled) | Fuzzy date parsing |

These are listed in the platform's `requirements.txt`.

---

## API Endpoints Used

| API | Endpoint | Method | Auth |
|---|---|---|---|
| WikiCFP | `http://www.wikicfp.com/cfp/servlet/tool.search` | GET | None |
| ConferenceAlerts | `https://conferencealerts.co.in/algeria` | GET | None |
| AllConferenceAlert | `https://www.allconferencealert.com/algeria.html` | GET | None |
| HuggingFace | `https://huggingface.co/api/models` | GET | None |
| arXiv | `http://export.arxiv.org/api/query` | GET | None |
| Semantic Scholar | `https://api.semanticscholar.org/graph/v1/paper/search` | GET | None |
| MIT OCW | `https://ocw.mit.edu/api/v0/search/` | GET | None |
| ROR | `https://api.ror.org/organizations` | GET | None |
| OpenAlex | `https://api.openalex.org/institutions` | GET | None (mailto) |

All APIs are **free and open**. No API keys are required.

---

## Phase 4 — Arabic, African & Algerian Source Expansion

Phase 4 expanded every scraper category with regional and specialised sources:

| Scraper | New Sources Added | Items |
|---|---|---|
| **Events** | ConferenceAlerts Algeria, AllConferenceAlert Algeria | Algerian academic conferences |
| **Tools** | 6 new HF queries (speech, LLMs), 10 curated LLMs/toolkits, 7 Arabic datasets | Arabic LLMs (Jais, AceGPT, ALLaM), speech models (Whisper, MMS), NLP toolkits (CAMeL, FARASA, Stanza) |
| **Courses** | 7 Coursera NLP courses, 7 YouTube NLP playlists | Online courses from DeepLearning.AI, IBM, Google Cloud, Stanford, HuggingFace, Arabic channels |
| **Institutions** | 10 Algerian universities, 10 African/Arabic NLP labs | USTHB, ESI, CERIST, Masakhane, InstaDeep, QCRI, CAMeL Lab, UM6P, KAUST |
| **News** | Improved S2 retry (5 retries, exponential backoff, 504/ConnectionError handling) | More reliable paper fetching |

### Semantic Scholar Rate-Limit Fix

The S2 API retry logic was upgraded:
- **Max retries:** 3 → 5
- **Backoff:** exponential `min(30 × 2^attempt, 180s)` instead of linear `15 × attempt`
- **New error handling:** 504 Gateway Timeout + ConnectionError retries
- **Retry-After header:** respected with +2s buffer
- **Warning removal:** error message that generated visible warnings was removed

---

## Phase 5 — Web Scraping Failure Handling & Improvements

Phase 5 hardened the scraping infrastructure with production-grade failure handling:

### Changes Summary

| Feature | Location | Description |
|---|---|---|
| **Retry + exponential backoff** | `base.py` `safe_request()` | Transient errors (429, 5xx, connection, timeout) retry up to `MAX_RETRIES` with exponential sleep |
| **User-Agent rotation** | `base.py` `_rotate_user_agent()` | 5-string UA pool, rotated per request attempt |
| **Circuit breaker** | `base.py` + `models.py` | `check_source()` / `report_success()` / `report_failure()` tied to `ScrapingSourceHealth` |
| **Source health score** | `ScrapingSourceHealth.health_score` | 0–100 float, −15 per failure, +10 per success |
| **Per-source failure tracking** | `ScrapingSourceHealth` model | Tracks total/consecutive failures, last error, avg response time |
| **Configurable timeout** | `BaseScraper.DEFAULT_TIMEOUT` | Class-level attribute (default 30s), overridable per scraper |
| **Structured error logs** | `base.py` `_log_error()` | Each error is a dict with type, message, source, URL, timestamp, extras |
| **Admin panel** | `admin.py` | Health bar, circuit badge, response time display in `ScrapingSourceHealthAdmin` |

### Circuit Breaker State Machine

```
                  success
    ┌──────────────────────────────┐
    │                              │
    ▼          failure ×3          │
  CLOSED ─────────────────────► OPEN
    ▲                              │
    │          cooldown elapsed    │
    │              (300s)          ▼
    │                          HALF-OPEN
    │          success             │
    └──────────────────────────────┘
              failure → re-OPEN
```

### Configurable Scraper Attributes

Sub-classes can override these class attributes:

```python
class MyCustomScraper(BaseScraper):
    DEFAULT_TIMEOUT = 45       # seconds per request
    MAX_RETRIES = 5            # retry attempts for transient errors
    BACKOFF_BASE = 3.0         # initial backoff sleep (seconds)
    BACKOFF_MAX = 120.0        # maximum backoff cap (seconds)
```

---

## Phase 6 — Scraping Intelligence

Phase 6 adds an intelligence layer that classifies, scores, and tracks every scraped item across four NLP research domains.

### New Module: `intelligence.py`

| Feature | Function | Description |
|---|---|---|
| **Keyword expansion** | `expand_keywords(seeds, max_results)` | Expands seed terms using a 4-domain ontology (~30+ keywords per domain, Arabic + English) |
| **Auto query generation** | `generate_queries(category, max_queries)` | Combines base terms × year modifiers + Arabic terms + category-specific extras |
| **Domain classification** | `classify_domain(text)` | Rule-based regex matching against ontology keywords; returns `{domain: confidence}` |
| **LLM fallback** | `classify_with_llm_fallback(text)` | Falls back to Groq LLM only when rule-based confidence < 0.5 (cost-efficient) |
| **Relevance scoring** | `compute_relevance_score(...)` | Weighted 0–100 score: recency (25%), relevance (30%), source health (15%), popularity (15%), completeness (15%) |
| **Trend detection** | `detect_trends(months)` | Analyses last N months of data: top domains, growing topics, top sources, category counts, monthly activity |

### Four Research Domains

| Domain Key | English Label | Description |
|---|---|---|
| `arabic_nlp` | Arabic NLP | Text processing, NER, sentiment analysis, morphology, tokenization |
| `arabic_languages` | Arabic Languages | Dialectology, MSA, corpus linguistics, linguistic resources |
| `speech_processing` | Speech Processing | ASR, TTS, speaker recognition, speech synthesis |
| `llm_research` | LLM Research | Large language models, fine-tuning, RLHF, prompt engineering |

Each domain has 30+ English keywords and 10+ Arabic keywords in the ontology.

### Scoring System

Items are ranked on a 0–100 scale using 5 weighted factors:

| Factor | Weight | Calculation |
|---|---|---|
| Recency | 25% | Tiered by age: <30 days = 100, <90 days = 80, <180 days = 60, <365 days = 40, else 20 |
| Relevance | 30% | Best domain match score × 100 |
| Source Health | 15% | `ScrapingSourceHealth.health_score` (0–100) |
| Popularity | 15% | `log10(downloads + citations + 1) / 7 × 100`, capped at 100 |
| Completeness | 15% | Proportion of optional fields present (description, website, Arabic content) |

### Integration with Scrapers

After every `scraper.run()`, the base class automatically:
1. Classifies each new result via `classify_domain()`
2. Computes a relevance score via `compute_relevance_score()`
3. Creates/updates a `ScrapedItemMeta` record with domain scores and ranking
4. Returns an `intelligence` summary in the result dict

### New Institutions (Phase 6)

**North African (10):** Mohammed V University (MA), Cadi Ayyad University (MA), International University of Rabat (MA), University of Tunis El Manar (TN), University of Sfax (TN), University of Sousse (TN), University of Tripoli (LY), Nile University (EG), E-JUST (EG), Ain Shams University (EG)

**Arabic/Gulf (10):** King Saud University (SA), KFUPM (SA), Khalifa University (AE), MBZUAI (AE), Qatar University (QA), American University of Beirut (LB), JUST (JO), Sultan Qaboos University (OM), University of Khartoum (SD), KINDI Center for AI (QA)

### New Events (Phase 6)

**10 Arabic/MENA conferences:** ICNLSP 2025 (Algiers), ArabicNLP 2025 (Vienna), ICALP 2025 (Rabat), AI & NLP Summit MENA 2025 (Dubai), North Africa AI Summit 2025 (Tunis), NADI 2025 (Vienna), Deep Learning Indaba 2025 (Dakar), IEEE AICCSA 2025 (Cairo), SIGARAB Workshop 2025 (Suzhou)

**New country scrapers:** ConferenceAlerts for Morocco, Tunisia, and Egypt.

### Trends API Endpoint

```
GET /<lang>/scraping/trends/?months=6
```

Returns JSON with:
- `top_domains` — Most active research domains with counts
- `growing_topics` — Domains with highest growth percentage
- `top_sources` — Healthiest and most productive sources
- `category_counts` — Items per category (events, tools, news, courses, institutions)
- `monthly_activity` — Items created per month

Staff-only access. `months` parameter is clamped to 1–24.

### Admin Panel

`ScrapedItemMeta` is registered in the admin with:
- Color-coded category badges
- Score badges (green ≥70, amber ≥40, red <40)
- Filters by category and primary domain
- Search by item title
- Ordered by highest relevance score

---

## Prompt — Section Experience (Style LinkedIn)

Copie-colle cette prompt pour guider l’implémentation:

```text
Tu es un développeur Django senior. Implémente la section “Experience” dans la page Profile avec un UX proche de LinkedIn.

Objectif principal
- Refaire la section Experience pour qu’elle soit claire, moderne, et orientée timeline professionnelle.
- Ajouter une petite action “+ Ajouter une expérience”.

Contraintes UX
1) Choix du thème avant affichage (Light / Dark / System).
2) La section Experience doit respecter le thème choisi (couleurs, contrastes, lisibilité).
3) Le bouton “+ Ajouter une expérience” doit être compact et visible en haut de la section.
4) Affichage en cartes/listes, triées par date début la plus récente.

Données obligatoires pour une expérience
- Nom de l’institution
- Rôle / poste
- Date de début
- Date de fin (optionnelle)

Règles métier
- Si la date de fin est vide: afficher le statut “En cours”.
- Si date de fin renseignée: afficher la période complète (Début → Fin).
- Validation: date début <= date fin (si date fin existe).
- Interdire institution et rôle vides.

Types d’expérience à supporter
- Professional (job, stage, freelance)
- Project (expérience projet)
- Event (organisation/participation à événement)

Comportement attendu
- Un formulaire modal ou inline s’ouvre via “+ Ajouter une expérience”.
- L’utilisateur choisit le type (Professional / Project / Event).
- Sauvegarde puis refresh immédiat de la liste.
- Chaque item affiche: institution, rôle, type, période, statut.

Exigences techniques (Django)
- Créer un modèle Experience relié à l’utilisateur.
- Champs recommandés: user, experience_type, institution_name, role_title, start_date, end_date, is_current, description, created_at, updated_at.
- Si is_current=true, end_date doit être null.
- Ajouter formulaire + validations backend.
- Ajouter vues CRUD minimales: create, update, delete.
- Ajouter rendu template dans Profile.
- Sécuriser: utilisateur ne modifie que ses propres expériences.

I18n
- Labels FR/AR/EN traduisibles.
- Le texte de statut doit être localisé (ex: “En cours” / “Ongoing” / “مستمر”).

Critères d’acceptation
- Le bouton “+ Ajouter une expérience” fonctionne.
- On peut créer une expérience avec institution + rôle + dates.
- Si pas de date fin, le statut “En cours” s’affiche.
- Les expériences Event et Project sont aussi ajoutables.
- Le rendu respecte le thème choisi.
```

