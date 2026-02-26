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
| **Events** | `events.Event` | WikiCFP + 12 curated conferences | ~12 events |
| **Tools** | `resources.NLPTool` | HuggingFace Hub API | ~44 tools |
| **News** | `QA.Post` | arXiv API + Semantic Scholar | ~20 papers |
| **Courses** | `resources.Course` | MIT OCW API + 10 curated courses | ~10 courses |
| **Institutions** | `institutions.Institution` | ROR API + OpenAlex API | ~66 institutions |

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
- **Curated List** — 12 major NLP conferences manually maintained in the source code (ACL, EMNLP, NAACL, COLING, EACL, AAAI, IJCNLP-AACL, ArabicNLP, LREC-COLING, SIGIR, NeurIPS, WANLP).

**How it works:**
1. Tries WikiCFP search with 3 different queries
2. Parses HTML rows (2 rows per event: title + dates/location)
3. Falls back to curated event list
4. For each event, resolves the organising institution (creates if needed)
5. Creates `events.Event` with all fields filled (title, description, dates, location, organizer, etc.)

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

**Source:** **HuggingFace Hub API** (`huggingface.co/api/models`) — A REST API that returns metadata for machine learning models. Searched with 8 queries focused on Arabic NLP models.

**How it works:**
1. Sends 8 separate API queries (arabic nlp, camelbert, arabert, arabic sentiment, etc.)
2. Deduplicates by model ID across queries
3. Maps HuggingFace pipeline tags to platform tool types (e.g., `text-classification` → `sentiment_analysis`)
4. Maps language tags (ar, en, fr, es) to platform language codes
5. Creates `resources.NLPTool` with model details, download counts, tags, and link

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
- **Curated List** — 10 well-known NLP courses from top universities (Stanford CS224N, CMU CS11-711, MIT 6.8610, McGill COMP 550, Oxford DL-NLP, NYU Abu Dhabi Arabic NLP, HuggingFace Course, Stanford SLP, ETH Multilingual NLP, UIUC Text Mining).

**How it works:**
1. Tries MIT OCW API search
2. Imports curated courses with full syllabi
3. For each course, resolves/creates the university institution
4. Creates `resources.Course` with all academic details

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

**How it works:**
1. Queries ROR with 4 keywords, deduplicates by ROR ID
2. Parses v2 format: extracts display name from `names[]`, location from `locations[].geonames_details`, website from `links[]`
3. Queries OpenAlex for 15 institutions
4. Parses geo data, works count, and citations count
5. Creates `institutions.Institution` with detailed descriptions

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

The scraping app defines two tracking models in `scraping/models.py`:

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

- Each scraper uses a shared `requests.Session` with a descriptive `User-Agent` header
- Timeouts are set to 30 seconds per request
- The HuggingFace scraper limits to 60 models across 8 queries
- The ROR and OpenAlex APIs are free and rate-limit-friendly
- arXiv requests respect the API's built-in pagination

### Error Handling

- Individual item failures don't crash the entire scraper run
- Errors are collected in `self.errors` list and logged
- The `ScrapingRun` record tracks all errors
- Network failures are caught by `safe_request()` and logged

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
- **Courses**: Edit `CURATED_COURSES` list in `scrapers/courses.py`
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
| WikiCFP returns no results | Site may be down or blocking | Curated events will still import |
| MIT OCW returns 404 | API endpoint deprecated | Curated courses will still import |
| Semantic Scholar returns 429 | Rate limit exceeded | Wait and retry; arXiv data still works |
| "Scraper error: ..." | Network timeout or API change | Check error logs; scraper records partial results |
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

Or use the Web Scraping dashboard in the admin panel — each category tab shows its recent runs.

---

## File Structure

```
scraping/
├── __init__.py                  # Django app init
├── admin.py                     # Django admin registration (ScrapingSource, ScrapingRun)
├── apps.py                      # Django app config
├── models.py                    # ScrapingSource + ScrapingRun models
├── urls.py                      # URL routing (dashboard + run endpoint)
├── views.py                     # Dashboard view + AJAX run_scraper endpoint
├── README.md                    # This documentation
│
├── scrapers/
│   ├── __init__.py              # Scraper registry (SCRAPERS dict, CATEGORY_META)
│   ├── base.py                  # BaseScraper abstract class (ES safety, HTTP, parsing)
│   ├── events.py                # EventScraper (WikiCFP + curated conferences)
│   ├── tools.py                 # ToolScraper (HuggingFace Hub API)
│   ├── news.py                  # NewsScraper (arXiv + Semantic Scholar)
│   ├── courses.py               # CourseScraper (MIT OCW + curated courses)
│   └── institutions.py          # InstitutionScraper (ROR + OpenAlex APIs)
│
├── management/
│   └── commands/
│       └── run_scraper.py       # CLI: python manage.py run_scraper --category <cat>
│
├── migrations/
│   ├── 0001_initial.py          # Initial migration
│   └── 0002_alter_scrapingsource_options_and_more.py
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
| HuggingFace | `https://huggingface.co/api/models` | GET | None |
| arXiv | `http://export.arxiv.org/api/query` | GET | None |
| Semantic Scholar | `https://api.semanticscholar.org/graph/v1/paper/search` | GET | None |
| MIT OCW | `https://ocw.mit.edu/api/v0/search/` | GET | None |
| ROR | `https://api.ror.org/organizations` | GET | None |
| OpenAlex | `https://api.openalex.org/institutions` | GET | None (mailto) |

All APIs are **free and open**. No API keys are required.
