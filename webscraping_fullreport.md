# 🕸️ Web Scraping Module Audit Report

## 1. 🏗️ Architecture Overview

The scraping module is designed around an extensible `BaseScraper` class, with specific scraper implementations inheriting from it. The architecture incorporates background processing, semantic deduplication, LLM-based validation, and data enrichment.

```text
                           +------------------------+
                           |  Celery Task (Beat)    |
                           +-----------+------------+
                                       |
                                       v
                           +------------------------+
   +---------------------->+      BaseScraper       +<----------------------+
   |                       +---+-------+--------+---+                       |
   |                           |       |        |                           |
+--v---------+ +---------------v-+ +---v--------v-+ +---------------+ +-----v-------+
|Events      | |News             | |Tools         | |Courses        | |Institutions |
|(WikiCFP)   | |(arXiv,Semantic) | |(HuggingFace) | |(MIT,Coursera) | |(ROR,OpenAlex|
+--+---------+ +---------------+-- +---+----------+ +---------------+ +-------+-----+
   |                           |       |        |                           |
   +---------------------------+-------+--------+---------------------------+
                                       |
                           +-----------v------------+
                           |   Enrichment Engine    | (Auto-translate, Infer labels)
                           +-----------+------------+
                                       |
                           +-----------v------------+
                           |    LLM Validation      | (Groq: Relevance, Spam, Schema)
                           +-----------+------------+
                                       |
                           +-----------v------------+
                           |   Semantic Embeddings  | (pgvector deduplication)
                           +-----------+------------+
                                       |
                           +-----------v------------+
                           |    Django Database     | (Save models, attach PDFs/Images)
                           +------------------------+
```

## 2. ✅ Fully Working Features

*   **Robust Base Engine (`base.py`)**: The `BaseScraper` provides solid foundation mechanisms including exponential backoff, circuit breaking (via `ScrapingSourceHealth`), language detection, duplicate checking, and database transaction safety.
*   **Five Specific Scrapers**:
    *   `events.py`: Integrates with WikiCFP and explicitly handles NLP-focused conferences.
    *   `news.py`: robustly imports from arXiv and Semantic Scholar APIs.
    *   `tools.py`: Scrapes from HuggingFace via API. Includes sophisticated model type detection.
    *   `courses.py` / `institutions.py`: Uses APIs (MIT OpenCourseWare, ROR, OpenAlex) mixed with static curated arrays of critical Arabic/NLP resources.
*   **Semantic Deduplication (`embeddings.py`)**: Uses `paraphrase-multilingual-MiniLM-L12-v2` and `pgvector` (`CosineDistance`) to prevent inserting duplicate items.
*   **LLM Validation (`llm_validation.py`)**: Evaluates unstructured data using Groq LLMs (llama-3.3-70b-versatile). Returns a strict JSON schema scoring relevance, quality, and detecting spam.
*   **Data Enrichment (`enrichment_engine.py` / `field_mapping.py`)**: Automatically translates between English and Arabic, calculates completeness scores, and infers standard choices based on text blobs.
*   **File Downloading (`file_downloader.py` and `pdf_utils.py`)**: Streams images/PDFs up to memory limits, safely extracts text up to 12k chars using `PyMuPDF` (`fitz`), and detects abstract/method/results sections using RegEx.
*   **Advanced Dashboard (`dashboard.html` / `views.py`)**: An asynchronous UI allows starting, tracking, and viewing scraper logs natively via Ajax polling of Celery's task statuses.

## 3. 🚧 Partially Built Features

*   **Custom Domain Scraping (`custom_scraper.py`)**: Implemented but restricted. The `soup.get_text()` is truncated to 6000 characters before sending it to the LLM, potentially cutting off the very content you want to scrape from large pages. The fallback CSS selector mechanism is primitive and relies on `<h2/3>` and adjacent `<p>` mapping, which usually fails on modern reactive web apps (e.g., React/Vue sites). 
*   **RSS Auto-Detection (`rss_scraper.py`)**: The scraper works perfectly for finding `feedparser` compatible feeds and extracts generic metadata but currently assumes *every* custom domain scraper feed has fields structured under generic names. It cannot parse sophisticated namespaces (like `<dc:creator>` or `<media:content>`).
*   **Scheduled Tasks**: Celery beat is functional and the tasks exist (`run_scraper_task` in `tasks.py`), but no schedule is hardcoded. It relies purely on an admin configuring `PeriodicTask` objects via Django's admin interface. Out of the box, nothing acts autonomously.

## 4. 🪲 Silent Errors and Bugs

### Critical Bugs
1.  **Sys User Fallback Violation (`base.py:101`)**: `self.get_system_user()` fetches the first `is_superuser=True`. If no superuser exists, it returns `None`. When models (e.g., `Event` or `Post`) attempt to save `created_by=None` and the field specifies `null=False` at the DB level, the scraper totally crashes.
2.  **Date Maths Failure (`intelligence.py:466`)**: In `compute_relevance_score`, timezone handling fallback can crash. Subtracting a naive `datetime.date` from a `datetime.datetime` object (which `timezone.now()` produces) throws `TypeError: can't subtract offset-naive and offset-aware datetimes`.
3.  **List to CharField Conversion Crash**: In `institutions.py`, `item_dict.get("research_specialties", [])` is passed to the DB model. If `Institution.research_specialties` is a `CharField` without an implicit ArrayConverter, it will be stored verbatim as a `['list', 'string']` representation or throw a database error. (Contrasts with `events.py`, which defensively converts: `if isinstance(domains_value, list): domains_value = ",".join(domains_value)`).

### Silent Exceptions Swallowing
1.  **Enrichment Engine (`enrichment_engine.py:108`)**: The batch translation LLM call contains a broad `try/except Exception:` that simply logs and reverts to English. If Groq's API structure changes or tokens hit limits, translations quietly disappear instead of throwing visible warnings to admins.
2.  **PDF Parsing (`pdf_utils.py:199`)**: `try/except Exception as e:` inside `extract_text` returns an empty string when `fitz.open()` fails. A corrupted PDF won't raise any visible error in the scrape logs, it just gets completely ignored.
3.  **Embeddings (`base.py:986`)**: Embedding generation is wrapped in `try/.../except Exception: pass`. If `SentenceTransformer` fails (e.g. OOM or mismatched tensors on a worker without a GPU/sufficient RAM), it silently inserts rows without embeddings, destroying future semantic deduplication for that item.

### Hardcoded/Static Data
*   **`courses.py` / `institutions.py`**: A large portion of `courses.py` (e.g., Stanford `CS224N`, Coursera, YouTube playlists) and `institutions.py` (Dz universities) relies heavily on hardcoded lists `CURATED_COURSES`, `YOUTUBE_PLAYLISTS`, `ALGERIAN_UNIVERSITIES`. These are *static imports* posing as scrapers. The dates inside these descriptions (e.g. '2024') will become quickly obsolete.

## 5. 📊 Field Completeness Per Scraper

The completeness status of major models mapped across scraping targets:

| Scraper Category | Key Required Fields | Missing/Weakly Filled Fields | Validation Minimum Threshold |
| :--- | :--- | :--- | :--- |
| **Events** | title, description, start_date | `location_ar`, `poster_url`, `submission_deadline` are rarely populated. | 40% |
| **Tools** | title, tool_type, access_link | `thumbnail_url`, `documentation_url` often missing from HuggingFace. | N/A |
| **News** | title, content, published_date | `authors`, `keywords` heavily rely on LLM fallback. | 40% |
| **Courses** | title, field_of_study, level | `syllabus_file_url`, `prerequisites` are non-existent outside the curated static list. | 40% |
| **Institutions**| name, type, country, city | `email`, `phone` are extremely sparse using OpenAlex/ROR. | 35% |

## 6. 🛡️ Validation System Status (`llm_validation.py`)

**Status:** Robust and Active.
*   **Features:** Evaluates items using Llama-3 (Groq API), identifying relevance, detecting spam, isolating quality scores (0-100), predicting field matches, and normalizing dates into ISO-8601 strings. 
*   **Fail-safes:** It enforces JSON structure parsing and implements a 2-retry circuit with exponential backoff.
*   **Observations:** The LLM schema enforcement relies on prompt-engineering (`EXPECTED_KEYS = {...}`) instead of Groq's newer JSON-Mode guarantee function, but works reasonably well.

## 7. 🧩 Enrichment System Status (`enrichment_engine.py`)

**Status:** Fully Working.
*   **Features:** Cross-links with `field_mapping.py` to identify missing keys, automatically maps categorization flags (like `academic_level="master"` by hunting for the word "graduate" in the blob), sets English-to-Arabic auto translation blocks.
*   **Observations:** Keywords are extracted using a local regex stop-word matcher (`_extract_keywords`) rather than using an LLM, which keeps it exceptionally fast but occasionally naive. 

## 8. 📥 File Downloading Status (`file_downloader.py`)

**Status:** Fully Working with strict constraints.
*   **Features:** Secures against memory leaks by chunk-streaming (`iter_content(8192)`). Limits size (15MB documents, 5MB images). Identifies 8 allowed MimeTypes and refuses everything else. Uses UUID for random safe filenames.
*   **Observations:** Fully isolated attachment pipeline `attach_file_to_model(...)` operates directly with Django's `FileField`.

## 9. 👯 Semantic Duplicate Detection Status (`embeddings.py`)

**Status:** Fully Working (Excellent implementation).
*   **Methodology:** Uses `SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')`. Computes distance using `CosineDistance` in Postgres (pgvector).
*   **Effectiveness:** An exact title match acts as layer 1 in `base.py`. If it misses, Layer 2 checks pgvector. Anything scoring > 0.88 similarity is rejected natively before hitting the database.

## 10. 📡 RSS Feed Support Status (`rss_scraper.py`)

**Status:** Partial.
*   **Features:** Implements a trial-and-error discovery across 12 standard URL combinations (e.g. `/feed.xml`, `/rss`). Parses with standard `feedparser`.
*   **Observations:** The data parsed from standard `<summary>` tags is pushed as the raw description. It doesn't crawl the RSS item tags to extract the full body text via an HTTP request, resulting in shallow snippets instead of full articles. 

## 11. 🌐 Custom Domain Scraping Status (`custom_scraper.py`)

**Status:** Functional but Brittle.
*   **Mechanism:** Leverages an LLM specifically instructed to structure data out of raw `page_text`. It heavily relies on BeautifulSoup `.get_text()` taking the top 6000 characters from a webpage. 
*   **Issues:** Modern web pages have significant header/nav clutter. The CSS Selector fallback expects you to supply standard selectors (e.g. `h2, h3` for titles), which administrators of the platform rarely know how to write.

## 12. ✍️ Arabic NLP Status (`intelligence.py`)

**Status:** Comprehensive Domain Authority.
*   **Ontology:** Houses a massive manually-maintained bidirectional English-Arabic ontology specifically mapping variations, dialects, architectures, and concepts related to Arabic Natural Language Processing.
*   **Classification:** Employs a blazing-fast Regex categorization before using LLM fallbacks, ensuring speed.

## 13. 📄 PDF Parsing Status (`pdf_utils.py`)

**Status:** Highly Resilient but text-only.
*   **Method:** Relies on PyMuPDF to extract text strings. Capable of locating structural zones (Abstract, Introduction, Result, References) using English, French, and Arabic translation markers (e.g. `\bالملخص\b`).
*   **Observations:** Does not implement OCR (Optical Character Recognition) fallback. If an old Arabic PDF is a scanned image, it will extract an empty string.

## 14. ⏳ Celery and Scheduling Status

**Status:** Infrastructure present, auto-automation absent.
*   **Queues:** Separated logically into `scraping`, `chatbot`, `documents`.
*   **Issues:** Celery beat is operational, but it acts globally. Scrapers are triggered on demand via the UI. You must manually add `django_celery_beat.PeriodicTask` via the admin panel to trigger scrapers automatically; no migrations setup this schedule by default.

## 15. 🧠 Intelligence Module Status (`intelligence.py`)

**Status:** Robust and Fully Integrated.
*   **Hardcoded Dates**: It uses `_current_year = str(datetime.datetime.now().year)` dynamically, meaning the intelligence module is **future-proof**. The only hardcoded element is in `courses.py` statically inserted tuples.
*   **Trend Detection**: `detect_trends(months=6)` algorithm is fantastic, successfully identifying topic velocities by isolating items over 6 month horizons. 

## 16. 📦 Installed Packages Audit
*   All required scraping dependencies (`beautifulsoup4`, `requests`, `feedparser`, `langdetect`, `lxml`) and ML requirements for duplicate detection/validation (`PyMuPDF`, `sentence-transformers`, `pgvector`, `pytz`, `groq`) are accounted for properly in `requirements.txt`.

## 17. ❌ What is Completely Missing
1.  **Proxies & Anti-Scraping Defenses**: `BaseScraper` uses a custom User-Agent, but `requests.get()` lacks rotational IPs, proxies, or cloudflare-bypass systems (e.g., `cloudscraper` or `selenium` / `playwright`). Heavily guarded platforms will immediately block the worker IP on execution.
2.  **Model Unit Tests**: Zero `.py` files inside the scraper directories simulate API boundaries or mock responses. A changed HTML class on `WikiCFP` or `arXiv` breaks the pipeline silently. 
3.  **OCR Support**: For old Arabic NLP conference papers saved as pure images inside PDFs, the current `pdf_utils.py` fails to grab textual data entirely.
4.  **No `source` Field Catching:** `custom_scraper.py` attempts to pass `source="custom_scrape"` into models like `Event.objects.create()`, which likely causes an unexpected kwargs failure as no models contain a direct "source" attribute without specific migrations.

## 18. 🎯 Priority Recommendations

| Priority | Task | Complexity | Explanation |
| :--- | :--- | :--- | :--- |
| **High** | Fix Model Save Constraints | Low | Refactor `created_by=sys_user` in `base.py:create()` to either gracefully assign to standard Anonymous placeholders or generate a dedicated "System Scraper Bot" user on migration. |
| **High** | Fix `intelligence.py` Date Maths | Low | Swap naive `datetime.date` subtracting from `now` to proper `django.utils.timezone` operations in `compute_relevance_score` to prevent crashing. |
| **High** | Validate `research_specialties` | Low | Update `Institution.objects.create(...)` in `institutions.py` to `", ".join(specialties)` guaranteeing it successfully writes mapping out as strings rather than risking DB mismatch. |
| **Medium** | Increase Custom Scraper LLM Token Window | Medium | Jump the 6000-char block limit in `custom_scraper.py` to 12000 chars since `llama-3.3-70b` has an excellent context window, enabling accurate extraction on highly dense web pages. |
| **Medium** | Schedule Syncs via Migrations | Low | Write a data migration that inherently schedules `django_celery_beat.models.PeriodicTask` objects to trigger run_scraper every 24-hours automatically. |
| **Medium** | Implement Headless Browser API | High | Integrate `playwright` or `selenium` for Custom Domain scraping to interact with React SPAs or sites guarding against standard `requests.Session()` polling. |
| **Low** | Move Curated Mock Data to JSON | Low | Strip `YOUTUBE_PLAYLISTS` and `CURATED_COURSES` out of `courses.py` into a `.json` fixture structure preventing the pollution of the operational scraping engine with manual dummy records. | 
