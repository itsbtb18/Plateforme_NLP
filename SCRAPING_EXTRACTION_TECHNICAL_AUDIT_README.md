# Scraping and Extraction Pipeline Technical Audit

Author role: Senior Data Engineer and Automation Expert
Date: 2026-04-18
Scope: Direct LLM extraction pipeline for Events, NLP Resources, and Laws-targeted requirements

---

## 1. Executive Summary

Your pipeline has evolved significantly and is no longer blocked by the old high-confidence hard stop. It now supports broad ingestion with review-first moderation and update tracking. However, several architectural and observability gaps still prevent true production-grade autonomy.

### Current maturity snapshot

- Strengths:
  - Direct LLM extraction with structured normalization is working.
  - Upsert behavior supports updates and review workflows.
  - Placeholder fallback exists for partial data handling.
  - Event discovery persistence exists via discovered URL queue model.

- Main weaknesses:
  - Metrics and run visibility are still inconsistent in some endpoints.
  - Autonomous discovery queue is persisted but not yet fully consumed in active scrape loops.
  - Cross-script multilingual dedup (Latin/Arabic variants) is not implemented.
  - Laws category is requested in product scope but not implemented as a dedicated scraper path.

### Efficiency score

Overall score: 7.2/10

- Ingestion robustness: 8.0
- Data quality controls: 7.0
- Discovery autonomy: 5.5
- Observability and run truthfulness: 6.0
- Multilingual entity matching: 5.0
- Upsert safety and moderation compatibility: 9.0

---

## 2. End-to-End Pipeline Analysis

## Stage A: Request and discovery

Flow:
1. Category run starts in Celery task orchestration.
2. Search queries are generated (DB queries or defaults).
3. Tavily returns search results with title, url, content.

Observed behavior:
- Empty content rows are dropped early by Tavily client normalization.
- Blocked hosts and listing-like sources are filtered before extraction.

Drop points:
- Empty-content search rows are removed.
- Source URL blocked host filters remove candidates.
- Search query exhaustion when DB queries are narrow and defaults are disabled.

Risk:
- Good event pages with thin snippets can be filtered before the LLM sees them.

---

## Stage B: HTML/text preparation

Flow:
- For direct extraction, you mostly rely on Tavily content and only limited local parsing.
- For discovery enrichment, optional BeautifulSoup selector scans and fallback heuristic URL extraction are used.

Observed behavior:
- There is no unified, deterministic HTML cleaning pipeline before LLM prompts.
- Content normalization is spread across modules, not centralized in a single pre-LLM cleaner.

Drop points:
- Over-truncated content budgets can suppress weak but valid event signals.

Risk:
- High variance prompt quality across sources and categories.

---

## Stage C: LLM prompting and extraction

Flow:
- LLM event extractor builds compact batched prompts from Tavily rows.
- Returns JSON array and normalizes fields.

Observed behavior:
- Source URL is mandatory in normalization; items without resolvable URL are dropped.
- Prompt fallback exists for malformed JSON and payload-too-large scenarios.

Drop points:
- Candidate dropped if source_url/url is missing after normalization.
- Candidate dropped if title/description viability checks fail.

Risk:
- Strict field requirements reduce false positives but can reduce recall on sparse pages.

---

## Stage D: Validation and confidence routing

Flow:
- Confidence score is computed via weighted completeness features.
- Validation quality messages are attached to notes.
- Review status is assigned from confidence percentage.

Observed behavior:
- Hard confidence rejection is currently disabled in quality validator.
- Review routing still marks <50 as REJECTED and >=50 as PENDING_REVIEW.

Drop points:
- Non-confidence hard checks still reject candidates in category-specific normalization gates.
- Some categories return None from _normalize_candidate when required base fields are absent.

Risk:
- Confusion between "not rejected by validator" and "still dropped by normalizer/upsert prerequisites".

---

## Stage E: Database upsert and moderation safety

Flow:
- Upsert uses transactional select_for_update patterns.
- Existing APPROVED rows are protected and only metadata plus NEEDS RESEARCH fields are updated.

Observed behavior:
- This is one of the strongest parts of your current pipeline.
- Pending and rejected records can be refreshed with newer data.

Drop points:
- Organizer resolution failures for events can still skip records.
- Allowed field filtering can silently discard extracted attributes not in model schema.

Risk:
- Good candidates may be skipped late due to relational dependency (organizer/institution creation failures).

---

## Stage F: Run counters and visibility

Flow:
- Task layer stores created, updated, skipped, and emits notifications.
- Some UI endpoints still compute simplified counters.

Observed behavior:
- Main run notifications now include updated counts.
- Legacy custom source endpoints still use len(results) as created count semantics.

Drop points:
- No data loss here, but severe visibility loss and incorrect interpretation by operators.

Risk:
- Operators misdiagnose runs as underperforming due to counter mismatch.

---

## 3. Critical Bugs (Logic Errors)

1. Created/updated semantic bug in custom source run views
- Symptom: items_created is assigned from len(results), which includes updated rows.
- Impact: created metric inflation and incorrect run status interpretation.
- Severity: High (observability correctness).

2. Legacy run item count fallback ignores updates
- Symptom: helper fallback uses created + skipped when items_found is unset; updated is excluded.
- Impact: dashboards can underreport actual processed volume.
- Severity: High.

3. Laws scope mismatch
- Symptom: product asks for Events, Laws, NLP Resources, but no dedicated laws scraper class/path found.
- Impact: scope gap between business requirements and pipeline implementation.
- Severity: High (functional coverage).

4. Discovery queue persisted but not fully operationalized as crawl frontier
- Symptom: DiscoveredURL is written and prioritized, but no strong evidence of active dequeue-and-process lifecycle with processed state transitions in normal runs.
- Impact: partial autonomy only; discovery does not reliably compound over time.
- Severity: Medium-High.

5. Multilingual dedup blind spots
- Symptom: dedup normalization relies on whitespace/lowercase and similarity; no transliteration/phonetic cross-script matching.
- Impact: ILMI vs علمي and similar pairs can survive as duplicates.
- Severity: Medium-High.

---

## 4. Partial Implementations (Existing but Rigid)

1. Self-healing selectors
- Present: CSS selectors + section-heading heuristics + LLM URL scan fallback.
- Rigid point: selector sets are static and site-specific confidence is not persisted as adaptive policy.

2. Autonomous discovery
- Present: discovered URL capture and prioritization command.
- Rigid point: frontier lifecycle and adaptive recrawl strategy are not yet fully automated end-to-end.

3. Graceful fallback
- Present: NEEDS RESEARCH placeholder logic is implemented in shared partial handler.
- Rigid point: not yet enforced as a single schema-level contract across all category normalizers.

4. Confidence policy
- Present: review routing is active and quality notes are collected.
- Rigid point: mixed semantics between validator pass/fail and downstream normalizer drops can confuse operators.

---

## 5. The 10/10 Intelligence Roadmap

## 5.1 Deduplication: exact -> fuzzy -> entity-smart

Implement a 3-layer dedup strategy:

Layer 1: Deterministic keys
- URL canonical hash
- Same title + same date
- DOI/arXiv/GitHub exact IDs

Layer 2: Fuzzy lexical
- Weighted token-set ratio
- Character n-gram similarity
- Date-window tolerance

Layer 3: Multilingual entity matching
- Arabic normalization (diacritics, alef variants, taa marbuta)
- Transliteration bridge (Buckwalter or CAMeL translit)
- Alias table for institutions/organizers
- Optional embedding similarity for title + organizer pairs

Target rule:
- Mark duplicates when score >= 0.88, soft-review when 0.78-0.88.

---

## 5.2 Self-healing selectors and layout drift resilience

Recommended architecture:
1. Keep selector bundles per host with confidence scores.
2. On extraction failure, run LLM structural probe to propose backup selectors.
3. Store selector outcomes in selector telemetry table.
4. Automatically promote selectors that pass consecutively N times.
5. Auto-disable selectors with sustained failure streak.

Operational metric:
- selector_success_rate per host per 24h
- automatic rollback to last-known-good selector set

---

## 5.3 Autonomous discovery via breadcrumb crawling

Implement a frontier pipeline:
1. Seed Tavily + configured queries.
2. Extract related URLs from sections and anchor context.
3. Push into frontier queue with priority_score.
4. Dequeue top-K unexplored URLs each run.
5. Mark processed with last_result_state (success/empty/fail).
6. Recrawl policy with exponential backoff by domain and result quality.

Must-have fields in frontier rows:
- first_seen_at, last_seen_at, last_crawled_at
- crawl_attempts, last_status_code, last_error
- depth, parent_url, anchor_text, source_reason

---

## 5.4 Graceful failure with NEEDS RESEARCH contract

Rule:
- Any kept item must have non-null required business fields.
- Missing values are replaced with NEEDS RESEARCH at normalization boundary.

Enforcement points:
- pre-validation normalization
- pre-upsert schema contract check
- post-save quality event for moderation dashboard

---

## 5.5 Observability and run truthfulness

Standardize run metrics everywhere:
- created
- updated
- skipped
- flagged_for_review
- hard_dropped_by_stage

Required dashboards:
- drop funnel by stage
- per-source acceptance ratio
- per-domain discovery yield
- duplicate collapse ratio

---

## 6. Refined Code Snippet: Validation Logic (Production Grade)

```python
# validation_router.py
from dataclasses import dataclass
from typing import Any

NEEDS_RESEARCH = "[NEEDS RESEARCH]"

@dataclass
class ValidationDecision:
    keep: bool
    review_status: str
    notes: list[str]
    hard_drop_reason: str | None = None


def to_confidence_percent(value: Any) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if v <= 1.0:
        v *= 100.0
    return max(0.0, min(100.0, v))


def fill_missing_required(payload: dict[str, Any], required_fields: list[str]) -> dict[str, Any]:
    out = dict(payload or {})
    for field in required_fields:
        val = out.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            out[field] = NEEDS_RESEARCH
    return out


def validate_and_route(
    payload: dict[str, Any],
    *,
    required_fields: list[str],
    hard_rules: list[callable],
) -> tuple[dict[str, Any], ValidationDecision]:
    candidate = fill_missing_required(payload, required_fields)
    notes: list[str] = []

    # Hard rules are explicit and observable.
    for rule in hard_rules:
        ok, reason = rule(candidate)
        if not ok:
            return candidate, ValidationDecision(
                keep=False,
                review_status="REJECTED",
                notes=notes,
                hard_drop_reason=reason,
            )

    confidence = to_confidence_percent(
        candidate.get("confidence_score", candidate.get("extraction_confidence"))
    )

    if confidence >= 50.0:
        status = "PENDING_REVIEW"
        candidate["approval_status"] = "pending"
    else:
        status = "REJECTED"
        candidate["approval_status"] = "rejected"
        notes.append("Auto-rejected: confidence_score below 50%")

    candidate["confidence_score"] = round(confidence, 1)
    candidate["scrape_status"] = status

    return candidate, ValidationDecision(
        keep=True,
        review_status=status,
        notes=notes,
        hard_drop_reason=None,
    )
```

---

## 7. Refined Code Snippet: Safe Save/Upsert Function

```python
# safe_upsert.py
from django.db import transaction

NEEDS_RESEARCH = "[NEEDS RESEARCH]"


def is_needs_research(value) -> bool:
    return isinstance(value, str) and value.strip().upper() == NEEDS_RESEARCH


def is_approved(obj) -> bool:
    scrape_status = str(getattr(obj, "scrape_status", "") or "").upper()
    approval_status = str(getattr(obj, "approval_status", "") or "").lower()
    return scrape_status == "APPROVED" or approval_status == "approved"


def filter_for_approved_record(existing_obj, incoming_defaults: dict, metadata_fields: set[str]) -> dict:
    safe = {}
    for k, v in incoming_defaults.items():
        if k in metadata_fields:
            safe[k] = v
            continue
        if not hasattr(existing_obj, k):
            continue
        existing_val = getattr(existing_obj, k)
        if is_needs_research(existing_val) and v not in (None, ""):
            safe[k] = v

    if hasattr(existing_obj, "scrape_status"):
        safe["scrape_status"] = str(getattr(existing_obj, "scrape_status") or "").upper()
    if hasattr(existing_obj, "approval_status"):
        safe["approval_status"] = str(getattr(existing_obj, "approval_status") or "").lower()
    return safe


def upsert_with_moderation_lock(model, lookup: dict, defaults: dict, metadata_fields: set[str]):
    with transaction.atomic():
        obj = model.objects.select_for_update().filter(**lookup).first()
        if obj is None:
            create_data = dict(defaults)
            create_data.update(lookup)
            return model.objects.create(**create_data), True

        effective_defaults = dict(defaults)
        if is_approved(obj):
            effective_defaults = filter_for_approved_record(obj, defaults, metadata_fields)

        for field_name, field_value in effective_defaults.items():
            setattr(obj, field_name, field_value)
        obj.save()
        return obj, False
```

---

## 8. 5 Advanced Search Queries for Untapped Sources

Use these as high-yield discovery seeds:

1. "Arabic NLP conference 2026 site:.edu OR site:.ac.uk OR site:.org call for papers"
2. "computational linguistics workshop MENA 2026 site:aclweb.org OR site:acm.org OR site:ieee.org"
3. "Arabic speech processing shared task 2026 site:github.com OR site:huggingface.co"
4. "NLP research seminar Arab university 2026 site:.edu.sa OR site:.edu.eg OR site:.dz"
5. "language technology challenge Arabic dialect 2026 event registration"

---

## 9. Immediate Implementation Priorities (Next 2 Sprints)

Sprint 1:
- Fix metric semantics in custom-source views and helper counters to include updated.
- Add explicit drop-reason counters by stage.
- Create a Laws scraper skeleton with shared base validation/upsert contracts.

Sprint 2:
- Wire discovered URL frontier dequeue into event scrape loop.
- Add multilingual alias/transliteration matching in dedup.
- Add selector telemetry and automatic fallback promotion.

---

## 10. Final Audit Verdict

Your core extraction and moderation-preserving upsert architecture is strong and close to production quality. The largest remaining gaps are not in model inference, but in frontier autonomy, multilingual dedup intelligence, and metric truthfulness across all endpoints.

Once those three are addressed, this module can move from strong engineering prototype to reliable production-grade ingestion system.
