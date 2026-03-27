# Hardcoded Analysis Report (`scraping/**`)

## Summary

| Category | Count |
|---|---:|
| Hardcoded URLs/domains | 33 |
| Hardcoded numeric thresholds/timeouts/limits | 44 |
| Hardcoded config-like strings (model/index/queue/etc.) | 11 |
| Incomplete implementations (TODO/FIXME/pass/placeholders) | 5 |
| Env vars referenced but not in `.env.example` | 5 |
| Copy-pasted logic across scrapers | 10 |
| Total findings | 108 |

Notes:
- `.env.example` exists at project root and includes several scraping vars, but some referenced vars are missing.
- Scope analyzed: `scrapers/base*.py`, `news.py`, `events.py`, `courses.py`, `institutions.py`, `tools.py`, `rss_scraper.py`, `custom_scraper.py`, `enrichment_engine.py`, `enrichment/*`, `tasks.py`, `checkpoint.py`, `dead_letter.py`, `robots_policy.py`, `file_downloader.py`, `metrics.py`, `models.py`, `views.py`, `management/commands/*.py`.

---

## scraping/dead_letter.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 8 | Hardcoded string/path | `logs/scraping_dead_letters` | Move to setting/env (for example `SCRAPING_DEAD_LETTER_DIR`). |
| 55 | Magic number / format token | `"%Y%m%d"` filename strategy | Keep format if intentional, but document retention and naming policy in settings/constants. |

## scraping/enrichment/__init__.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Lazy import proxy only | No action. |

## scraping/enrichment/category_enrichers.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Thin wrapper mixin | No action. |

## scraping/enrichment/external_apis.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Thin wrapper mixin | No action. |

## scraping/enrichment/field_fillers.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Thin wrapper mixin | No action. |

## scraping/enrichment_engine.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 67 | Numeric threshold | `GroqLLMClient(timeout=30)` | Use global scraping/LLM timeout setting only (single source of truth). |
| 702 | Env var missing in `.env.example` | `GITHUB_TOKEN` | Add to `.env.example` with description and expected scope. |
| 721 | Hardcoded URL/domain | `https://api.github.com/repos/{repo_path}` | Move API base to config (`SCRAPING_GITHUB_API_BASE`). |
| 771 | Hardcoded URL/domain | `https://api.semanticscholar.org/...` | Move to source config or central API endpoints config. |
| 795 | Hardcoded URL/domain | `https://export.arxiv.org/abs/...` | Centralize arXiv endpoints in settings/constants shared with news scraper. |
| 953 | Hardcoded URL/domain | `https://api.openalex.org/institutions/...` | Move OpenAlex base URL to config. |
| 1079,1088 | Numeric timeout | `timeout=15` | Reuse shared HTTP timeout profile (`connect/read/total`) rather than local literals. |
| 1043 | Numeric threshold | `max_topics=5` | Externalize as enrichment setting (`SCRAPING_ENRICH_MAX_TOPICS`). |
| 1200 | Numeric threshold | `max_keywords=8` | Externalize to settings (`SCRAPING_ENRICH_MAX_KEYWORDS`). |

## scraping/file_downloader.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 53 | Env var missing in `.env.example` | `SCRAPING_MAX_DOCUMENT_MB` | Add to `.env.example` and document defaults. |
| 56 | Env var missing in `.env.example` | `SCRAPING_MAX_IMAGE_MB` | Add to `.env.example` and document defaults. |
| 52,55 | Numeric thresholds | defaults `50` MB document, `10` MB image | Keep but define in central scraping settings class for consistency. |
| 221 | Numeric timeout | default `timeout=30` | Use same timeout policy as base scraper config. |
| 263 | Numeric timeout | `HEAD timeout=10` | Configure separately (`SCRAPING_HEAD_TIMEOUT`) or derive from connect timeout. |
| 271 | Magic number | stream chunk size `8192` | Define constant (`DOWNLOAD_CHUNK_BYTES`) with rationale. |
| 59-67 | Hardcoded network blocks | RFC1918/link-local CIDRs | Keep for security but move to explicit security policy config for maintainability. |
| 202 | Hardcoded UA string | `Mozilla/5.0 NLPPlatformBot/1.0` | Move UA to centralized bot identity setting. |

## scraping/management/commands/__init__.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Empty file | No action. |

## scraping/management/commands/discover_selectors.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 24 | Numeric threshold | `sample-count default=5` | Expose as setting/default constant for discovery jobs. |
| 67-81 | Placeholder/partial selector mapping | empty selector fallback `""` for title/desc/date/author | Prefer explicit null/absent fields and validation to avoid silent weak configs. |

## scraping/management/commands/reactivate_sources.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Simple reset command | No action. |

## scraping/management/commands/run_scraper.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 39-41 | Magic number | separator width `50` (`'─' * 50`) | Move CLI formatting widths to constants if reused. |

## scraping/management/commands/seed_scraping_sources.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 7-78 | Hardcoded URLs/domains | `sigarab.github.io`, `aclanthology.org`, `conferencealerts`, `huggingface`, `semanticscholar`, `arxiv`, `coursera`, `youtube`, `mesrs`, `openalex`, `ror`, etc. | Move seed list to data file (`fixtures`/YAML/JSON) and load via command option. |
| 83 | Hardcoded behavior string | seed only when table empty | Consider `--force`, `--append`, and `--replace` modes configurable. |

## scraping/management/commands/show_schedules.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 21-24 | Magic numbers | fixed table widths in header | Use format constants or dynamic width. |
| 29-33 | Numeric thresholds | `24` hour day conversion logic | Keep but define named constants (`HOURS_PER_DAY`). |

## scraping/management/commands/sync_scraping_schedules.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 62-68 | Hardcoded strings | legacy task names list | Move legacy aliases to schedule config module for one source of truth. |

## scraping/management/commands/verify_scraping_media.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 16-36 | Hardcoded model/media mapping | per-category field tuples | Move mapping to shared media policy config to avoid drift with scrapers. |
| 110-136 | Copy-pasted logic across scrapers | manual `if category == ... import ...Scraper` factory | Replace with central registry/factory used elsewhere (`get_scraper`). |

## scraping/metrics.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 18,62 | Numeric thresholds | histogram buckets hardcoded | Extract bucket profiles into metrics settings. |
| 92 | Numeric thresholds | enrichment buckets `(0.01..30)` | Move to config; document why these ranges fit workload. |
| 198 | Numeric threshold | `min_interval_seconds=60` | Make configurable (`SCRAPING_METRICS_LAG_INTERVAL`). |
| 145 | Hardcoded mapping default | unknown skip reason maps to `similarity` | Add explicit fallback category (`unknown`) to avoid semantic conflation. |

## scraping/models.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 18 | Numeric threshold | `SCRAPING_CIRCUIT_THRESHOLD` default `25.0` | Align default with `.env.example` semantics and document scoring scale. |
| 19 | Env var missing in `.env.example` | `SCRAPING_CIRCUIT_TRIP_COUNT` | Add to `.env.example`. |
| 273-275 | Numeric thresholds | `FAILURE_PENALTY=15`, `SUCCESS_RECOVERY=10` | Move to configurable circuit policy block. |
| 542 | Hardcoded config-like string | embedding note `paraphrase-multilingual-MiniLM-L12-v2` | Promote embedding model name to setting; avoid embedding-specific literals in model metadata text. |
| 246 | Numeric threshold | `circuit_cooldown_seconds=300` | Reuse global circuit cooldown setting. |

## scraping/robots_policy.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 9 | Numeric threshold | `ROBOTS_CACHE_TTL = 3600` | Make TTL configurable per environment. |
| 37 | Policy choice | fail-open on exceptions (`return True`) | Keep if intentional, but make policy explicit/configurable (`SCRAPING_ROBOTS_FAIL_OPEN`). |

## scraping/scrapers/base.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 39-43 | Numeric thresholds | connect/read/total timeout `3/7/10` | Move to settings object only; avoid local literals. |
| 54-66 | Hardcoded strings/UA | full UA list and GitHub URL in bot UA | Move UA pool to config file for easier governance. |
| 94 | Numeric threshold | `MAX_RETRIES = 1` override | Derive from setting only; avoid hidden override. |
| 850-851 | Numeric window | dedup date overlap `±3 days` | Make per-category tolerance configurable. |
| 873,949,991,999,1032 | Similarity thresholds | `0.85/0.90` rules | Centralize dedup thresholds in policy config. |
| 1068,1074 | Similarity threshold | semantic fallback `0.88` | Move to setting and log exact computed score if available. |
| 1651 | Magic number | `truncate(..., max_len=200)` | Promote to named constant. |
| 1762 | Numeric thresholds | `max_days_past=30`, `max_days_future=730` | Externalize validation windows. |
| 1922,1944-1949,1980 | Numeric thresholds | freshness windows (`365`, `30`, `730`) | Move to category freshness policy config. |
| 478,493,502,516,546 | Hardcoded URLs/domains | arXiv/GitHub/avatar/YouTube URL builders | Keep builders but define endpoint bases as constants in one place. |

## scraping/scrapers/base_dedup.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Delegating mixin only | No action. |

## scraping/scrapers/base_http.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Delegating mixin only | No action. |

## scraping/scrapers/base_http_scraper.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 25 | Numeric thresholds | `TIMEOUT_SETTINGS = (3.0, 7.0)` | Reuse base timeout config object instead of duplicate constants. |
| 31 | Numeric threshold | `PLAYWRIGHT_THRESHOLD` default `200` | Move threshold to scraping settings and document text-length rationale. |
| 211 | Numeric threshold | `Wayback max_age_days=90` | Expose as setting (`SCRAPING_WAYBACK_MAX_AGE_DAYS`). |
| 49 | Hardcoded config-like string | redis alias `"default"` | Make cache alias configurable for scraping subsystem. |

## scraping/scrapers/base_media.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 53 | Hardcoded domain pattern | `"arxiv.org/pdf/"` in PDF URL heuristic | Move URL-domain heuristics to configurable pattern list. |

## scraping/scrapers/base_text.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| - | No finding | Delegating mixin only | No action. |

## scraping/scrapers/courses.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 144-175 | Hardcoded URLs/domains | e-learning DZ, CERIST, FUN-MOOC, Rwaq, Edraak, MIT, fast.ai, HuggingFace, DeepLearning.AI | Move source catalog to DB or external source manifest. |
| 198-260 | Hardcoded source metadata | tier source dicts with country/type/base_url | Keep in config data, not class constants. |
| 366,424,653,733,979,1034,1090,1388 | Numeric timeout | repeated `timeout=10` | Use per-source timeout from source config with fallback from settings. |
| 471,893,1279,1315 | Numeric timeout | `timeout=15` | Same as above. |
| 871-873 | Hardcoded numeric limits | MIT queries each `limit=10` | Externalize query limits. |
| 1252 | Env var missing in `.env.example` | `YOUTUBE_API_KEY` | Add to `.env.example`. |
| 1267-1268 | Hardcoded URL/domain | YouTube API endpoints | Move to provider endpoint config. |
| 1781 | Numeric threshold | `max_age_days=730` | Move to freshness policy settings. |
| 830 | Copy-pasted logic | RSS autodiscovery + parse loop | Move to base helper (`scrape_from_rss_sources`). |

## scraping/scrapers/custom_scraper.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 373-375 | Placeholder selectors | defaults `h2,h3`, `p`, `a` | Treat as fallback profile config; avoid silent generic extraction in production. |
| 109-120 | Hardcoded cleanup tags | fixed HTML tags removed list | Extract to configurable extraction profile by category/source type. |
| 50 | Hardcoded config-like taxonomy | `tokenization/stemming/ner/...` keyword map | Store in configurable classification rules file. |

## scraping/scrapers/events.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 13-16 | Hardcoded constants | `PRIORITY_SCORE['global']=25`, default discovery paths list | Move to event source policy config table/settings. |
| 82,149 | Numeric timeout | fallback timeout `20` | Use source-level timeout from DB config and global defaults. |
| 156 | Numeric limit + copy-paste logic | RSS parse `max_items=50` (same pattern in other scrapers) | Centralize RSS ingestion utility in base class. |
| 219 | Numeric magic number | container cap `containers[:180]` | Define constant with explanation. |
| 653-654 | Magic numbers | source acronym truncation to `10`, token cap `6` | Define as named constants. |

## scraping/scrapers/institutions.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 72-77 | Hardcoded domains | social-domain to platform map (`twitter.com`, `x.com`, `linkedin.com`, etc.) | Move mapping to shared URL normalization config. |
| 81-85 | Hardcoded URLs/domains | Algerian university scan list | Move to data source config (DB/fixture). |
| 93-142 | Hardcoded global lab websites | Stanford, MIT CSAIL, CMU, Edinburgh, JHU, CAMeL, QCRI, MBZUAI | External source manifest + sync command. |
| 151-216 | Hardcoded tiered source lists | TIER_1..4 RSS source dicts | Externalize to DB or fixture-driven source definitions. |
| 231-233 | Hardcoded API base URLs | ROR/OpenAlex endpoints | Move to API endpoint config. |
| 588,1092,1115,1142 | Hardcoded contact string | `mailto=platform@nlp-research.org` | Move to setting (for example `OPENALEX_MAILTO`). |
| 442,1187 | Numeric timeout | `timeout=10` | Use shared source timeout policy. |
| 590,827 | Numeric timeout | `timeout=20` | Use shared policy. |
| 1090,1117,1144 | Numeric timeout | `timeout=15` | Use shared policy. |
| 701 | Copy-pasted logic | RSS autodiscovery + parse loop | Move to base RSS helper. |

## scraping/scrapers/news.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 46-59 | Hardcoded URLs/domains | DGRSDT/MESRS/CERIST and Algerian university research URLs | Use source DB/fixtures instead of class constants. |
| 107,117,123,129,146 | Hardcoded numeric limits | `max_articles=15/18/20` | Move to source profile config. |
| 170 | Numeric limit + copy-paste logic | RSS parse `max_items=50` | Centralize shared RSS flow. |
| 371 | Hardcoded URL/domain | `http://export.arxiv.org/api/query` | Use configurable endpoint constant; prefer HTTPS if supported. |
| 386,466 | Numeric API limit | `max_results/limit=20` | Externalize to API query policy config. |
| 513 | Numeric retries | `_s2_request(...max_retries=5)` | Move to settings. |
| 522 | Numeric timeout | Semantic Scholar timeout `30` | Reuse shared HTTP timeout policy. |
| 529 | Magic number | retry buffer `+2` seconds | Define named constant (`RETRY_AFTER_BUFFER_SECONDS`). |
| 531 | Backoff magic numbers | exponential with base `30`, cap `180` | Move backoff profile to config. |
| 719 | Incomplete implementation | `pass` in title handling branch | Either implement translated-title behavior or remove dead branch. |

## scraping/scrapers/rss_scraper.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 20-27 | Hardcoded feed paths | `/feed`, `/rss`, `/atom.xml`, etc. | Move feed-path candidates to settings profile. |
| 63,93 | Numeric timeout | `timeout=10` | Use shared timeout policy. |
| 120 | Numeric default | `max_items=50` | Move to RSS settings default. |
| 326 | Numeric default | `_try_fetch_full_content(max_chars=3000)` | Expose as setting. |
| 333 | Numeric timeout | `timeout=15` | Use shared timeout policy. |
| 204 | Numeric threshold | short description cutoff `<200` | Externalize to setting with rationale. |

## scraping/scrapers/tools.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 110-111 | Hardcoded URLs/domains | HuggingFace model/dataset API bases | Move to provider endpoint config. |
| 181-202 | Hardcoded source URLs/domains | ESI/USTHB/CAMeL/Farasa/QCRI source list | External source manifest (DB/fixture). |
| 233 | Hardcoded URL/domain | PapersWithCode API endpoint | Move to config. |
| 264-266 | Hardcoded source URLs/domains | HuggingFace blog/PapersWithCode/Masakhane | Move to source config. |
| 282-512 | Hardcoded curated models/datasets | many static HuggingFace/Paper/Demo URLs | Keep in curated dataset file (JSON/YAML), not code constants. |
| 757,901 | Numeric limits | API limits `15`, `30` | Externalize to provider query config. |
| 683 | Copy-pasted logic | RSS autodiscovery + parse loop | Move to base RSS helper utility. |

## scraping/tasks.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 160,286,660 | Hardcoded config-like string | Celery queue name `"scraping"` | Move to setting (for example `SCRAPING_CELERY_QUEUE`). |
| 160,286,660 | Hardcoded task names | `scraping.tasks.*` | Consider central task name constants to avoid drift. |
| 618 | Magic number | dead-letter `retry_count=0` | Tie to retry policy state rather than literal. |

## scraping/checkpoint.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 11 | Hardcoded string/path | `logs/scraping_checkpoints` | Move to configurable checkpoint directory setting. |
| 12 | Numeric threshold | `CHECKPOINT_TTL = 86400 * 3` | Externalize TTL and document retention policy. |
| 49 | Magic number | SHA256 prefix length `[:16]` | Define named constant for token length. |

## scraping/views.py

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| 710,1280 | Numeric rate limit | `60 requests / 60s` | Centralize endpoint rate limits in settings map. |
| 771,1463 | Numeric rate limit | `5 requests / 60s` | Same centralization. |
| 834,862,1017,1029,1044,1068 | Numeric rate limit | `30 requests / 60s` | Same centralization. |
| 1550 | Numeric rate limit | metrics limit `10 / 60s` | Same centralization. |
| 385,579,1056,1061 | Numeric limit | recent runs limit `10` | Move to dashboard config constant. |
| 1178,1211,1219,1231,1258 | Numeric timeout | source test cache TTL `1800` | Move to setting (`SCRAPING_SOURCE_TEST_TTL_SECONDS`). |
| 229-248 | Hardcoded domain heuristics | tier inference tokens (`.dz`, `alger`, `mena`, `masakhane`, etc.) | Replace with weighted rules config or managed taxonomy. |
| 282 | Numeric threshold | fallback dedup confidence `85.0` | Reuse dedup threshold config from base policy. |

---

## Copy-paste Candidates Across Scrapers

The following logic appears repeatedly and should be promoted into shared base helpers:

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| `scraping/scrapers/events.py:156` | Copy-pasted logic | RSS discover + parse + normalize loop | Create `BaseScraper.scrape_rss_sources(...)`. |
| `scraping/scrapers/news.py:170` | Copy-pasted logic | Same RSS flow | Reuse shared helper. |
| `scraping/scrapers/courses.py:830` | Copy-pasted logic | Same RSS flow | Reuse shared helper. |
| `scraping/scrapers/institutions.py:701` | Copy-pasted logic | Same RSS flow | Reuse shared helper. |
| `scraping/scrapers/tools.py:683` | Copy-pasted logic | Same RSS flow | Reuse shared helper. |
| `scraping/scrapers/news.py:203` | Copy-pasted logic | list-page `safe_request(... timeout=10)` + candidate extraction | Factor shared listing fetch/paginated extraction helper. |
| `scraping/scrapers/events.py:171` | Copy-pasted logic | list-path iteration + `safe_request` + parse blocks | Factor into base utility. |
| `scraping/scrapers/courses.py:366` | Copy-pasted logic | list fetch + timeout + parse loops | Factor into base utility. |
| `scraping/scrapers/institutions.py:442` | Copy-pasted logic | list fetch + timeout + parse loops | Factor into base utility. |
| `scraping/management/commands/verify_scraping_media.py:110` | Copy-pasted logic | category-to-scraper import if-chain | Replace with central scraper registry lookup. |

---

## Env Vars Referenced But Missing In `.env.example`

| Line number | Type | Value | Recommendation |
|---:|---|---|---|
| `scraping/enrichment_engine.py:702` | Env missing | `GITHUB_TOKEN` | Add to `.env.example` with usage note (GitHub API enrichment). |
| `scraping/file_downloader.py:53` | Env missing | `SCRAPING_MAX_DOCUMENT_MB` | Add to `.env.example` (document size limit). |
| `scraping/file_downloader.py:56` | Env missing | `SCRAPING_MAX_IMAGE_MB` | Add to `.env.example` (image size limit). |
| `scraping/models.py:19` | Env missing | `SCRAPING_CIRCUIT_TRIP_COUNT` | Add to `.env.example` (breaker trip count). |
| `scraping/scrapers/courses.py:1252` | Env missing | `YOUTUBE_API_KEY` | Add to `.env.example` (optional YouTube API path). |
