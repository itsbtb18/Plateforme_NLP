#!/usr/bin/env python
"""
End-to-End Scraping System Test v2
===================================
Tests: Tavily search → LLM Extraction (Gemini-first) → Confidence scoring
for all 6 categories with 3 queries each (18 total).
"""
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
import django
django.setup()

from scraping.api_key_manager import api_key_manager
from scraping.network.search_client import TavilySearchClient
from scraping.extractors.core.llm_validation import GroqLLMClient, _extract_json
from scraping.intelligence import ConfidenceCalculator

logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")
for noisy in ["scraping", "llm_validation", "django", "channels", "daphne", "urllib3", "httpx"]:
    logging.getLogger(noisy).setLevel(logging.CRITICAL)
logger = logging.getLogger("e2e_test")
logger.setLevel(logging.INFO)

QUERIES = {
    "events": [
        "Arabic NLP conference 2025 2026",
        "computational linguistics workshop ACL EMNLP 2026",
        "natural language processing summit call for papers",
    ],
    "tools": [
        "Arabic NLP open source library GitHub 2025",
        "Arabic text processing Python toolkit",
        "Arabic speech recognition deep learning tool",
    ],
    "news": [
        "Arabic large language model research 2026",
        "multilingual NLP transformer Arabic 2025",
        "Arabic BERT GPT fine-tuning paper arxiv",
    ],
    "courses": [
        "Arabic NLP online course 2025 2026",
        "natural language processing Arabic certification",
        "deep learning for Arabic text Coursera edX",
    ],
    "corpus": [
        "Arabic dataset NLP HuggingFace 2025",
        "Arabic text corpus benchmark download",
        "Arabic speech dataset open access",
    ],
    "opportunities": [
        "NLP researcher position Arabic language 2025 2026",
        "postdoc natural language processing Arabic",
        "PhD position computational linguistics Arabic NLP",
    ],
}

confidence_calc = ConfidenceCalculator()

def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "***"
    return f"...{key[-6:]}"


def build_llm_prompt(category, content, url, title):
    system = (
        "You are an expert data extractor for Arabic NLP resources. "
        "Extract structured metadata from the provided web content. "
        "Return ONLY valid JSON. Do NOT include markdown fences."
    )
    field_guides = {
        "events":        '{"title_en":"...", "description_en":"...", "start_date":"YYYY-MM-DD", "end_date":"YYYY-MM-DD", "location_en":"...", "source_url":"...", "url":"..."}',
        "tools":         '{"title_en":"...", "description_en":"...", "tool_type":"...", "access_link":"...", "source_url":"...", "url":"..."}',
        "news":          '{"title_en":"...", "description_en":"...", "published_date":"YYYY-MM-DD", "source_url":"...", "url":"..."}',
        "courses":       '{"title_en":"...", "description_en":"...", "platform":"...", "url":"...", "source_url":"..."}',
        "corpus":        '{"dataset_name":"...", "description_en":"...", "download_url":"...", "source_url":"...", "url":"..."}',
        "opportunities": '{"job_title":"...", "description":"...", "institution_name":"...", "url":"...", "source_url":"..."}',
    }
    user = (
        f"Category: {category}\nURL: {url}\nTitle: {title}\n"
        f"Content:\n{content[:2500]}\n\n"
        f"Extract metadata as JSON matching this schema:\n{field_guides.get(category, '{}')}"
    )
    return system, user


async def run_tavily_search(client, category, query):
    method = getattr(client, f"search_{category}", None) or client.search_web
    return await method(query)


async def main():
    print("=" * 80)
    print("  ÉTAPE 1 — Configuration Check")
    print("=" * 80)

    groq_keys = api_key_manager.providers.get("groq", [])
    gemini_keys = api_key_manager.providers.get("gemini", [])
    tavily_keys = api_key_manager.providers.get("tavily", [])

    print(f"\n  Tavily API Keys : {len(tavily_keys)} configured")
    for i, k in enumerate(tavily_keys):
        print(f"    Key {i}: {mask_key(k)}")
    print(f"  Groq API Keys  : {len(groq_keys)} configured")
    print(f"  Gemini API Keys: {len(gemini_keys)} configured")

    categories = list(QUERIES.keys())
    print(f"\n  6 Categories: {', '.join(categories)}")

    tavily = TavilySearchClient()
    print(f"\n  Tavily enabled: {tavily.is_enabled}")
    if not tavily.is_enabled:
        print(f"  ⚠ Tavily disabled: {tavily.disabled_reason}")
        return

    llm = GroqLLMClient()
    print(f"  LLM configured: {llm.is_configured}")
    print(f"  LLM primary: {llm.primary_provider} | fallback: {llm.fallback_provider} | mode: {llm.mode}")

    # ── Quick LLM connectivity test ──
    print(f"\n  Quick LLM connectivity test...")
    
    # Test Gemini directly first
    gemini_ok = False
    try:
        t0 = time.time()
        r = llm._chat_with_gemini("Return exactly: OK", "Say OK")
        dt = time.time() - t0
        if r:
            gemini_ok = True
            print(f"    ✓ Gemini: responded in {dt:.1f}s")
        else:
            print(f"    ✗ Gemini: returned None (status={llm.last_status_code})")
    except Exception as e:
        print(f"    ✗ Gemini: {type(e).__name__}: {e}")

    # Test Groq directly
    groq_ok = False
    try:
        t0 = time.time()
        r = llm._chat_with_groq("Return exactly: OK", "Say OK")
        dt = time.time() - t0
        if r:
            groq_ok = True
            print(f"    ✓ Groq: responded in {dt:.1f}s")
        else:
            print(f"    ✗ Groq: returned None (status={llm.last_status_code}, err={llm.last_error_message[:80]})")
    except Exception as e:
        print(f"    ✗ Groq: {type(e).__name__}: {e}")

    if not gemini_ok and not groq_ok:
        print("\n  ⛔ Both LLM providers are down. Cannot run extraction tests.")
        print("     Continuing with Tavily-only test...\n")

    # Decide which provider to use for extraction
    def call_llm(system, user):
        """Call LLM with smart provider selection, bypassing TS service."""
        if gemini_ok:
            res = llm._chat_with_gemini(system, user)
            if res:
                return res
        if groq_ok:
            res = llm._chat_with_groq(system, user)
            if res:
                return res
        # Last resort: try both via _chat (includes TS service attempt)
        return llm._chat(system, user)

    print("\n" + "=" * 80)
    print("  ÉTAPE 2 & 3 — Running scraping tests (18 queries)")
    print("=" * 80)

    results_by_category = defaultdict(lambda: {
        "queries": 0, "tavily_ok": 0, "tavily_results": 0,
        "validated": 0, "extracted": 0, "confidence_scores": [],
        "duplicates": 0, "errors": [], "details": [],
        "key_rotations": 0, "providers_used": [],
    })

    all_extracted_titles = set()
    total_start = time.time()
    query_num = 0

    for category in categories:
        cat_queries = QUERIES[category]
        print(f"\n{'─' * 70}")
        print(f"  Category: {category.upper()} ({len(cat_queries)} queries)")
        print(f"{'─' * 70}")

        for query in cat_queries:
            query_num += 1
            cat_data = results_by_category[category]
            cat_data["queries"] += 1
            print(f"\n  [{query_num}/18] Query: \"{query}\"")

            # ── Tavily Search ──
            tavily_results = []
            tavily_key_before = api_key_manager.get_current_index("tavily")
            current_key = api_key_manager.get_current_key("tavily")
            try:
                t0 = time.time()
                tavily_results = await run_tavily_search(tavily, category, query)
                elapsed = time.time() - t0
                cat_data["tavily_ok"] += 1
                cat_data["tavily_results"] += len(tavily_results)
                tavily_key_after = api_key_manager.get_current_index("tavily")
                rotated = " [ROTATED]" if tavily_key_after != tavily_key_before else ""
                print(f"    ✓ Tavily: {len(tavily_results)} results in {elapsed:.1f}s (key: {mask_key(current_key or '')}){rotated}")
            except Exception as exc:
                err = f"Tavily: {type(exc).__name__}: {str(exc)[:80]}"
                cat_data["errors"].append(err)
                print(f"    ✗ {err}")
                continue

            if not tavily_results:
                print(f"    ⚠ No results, skipping extraction.")
                continue

            # ── Validate + Extract top 4 results ──
            validated_count = 0
            extracted_count = 0

            for idx, result in enumerate(tavily_results[:5]):
                url = result.get("url", "")
                title = result.get("title", "")
                content = result.get("content", "")

                if url == "tavily://answer" or not url.startswith("http"):
                    continue
                if not content or len(content.strip()) < 20:
                    continue

                validated_count += 1

                # ── LLM Extraction ──
                try:
                    sys_p, usr_p = build_llm_prompt(category, content, url, title)
                    t0 = time.time()
                    raw_response = call_llm(sys_p, usr_p)
                    llm_elapsed = time.time() - t0

                    if raw_response:
                        parsed = _extract_json(raw_response)
                        if parsed and isinstance(parsed, dict):
                            parsed.setdefault("source_url", url)
                            parsed.setdefault("url", url)

                            conf_report = confidence_calc.calculate(category, parsed)
                            conf_score = conf_report.get("percent", 0)
                            cat_data["confidence_scores"].append(conf_score)

                            item_title = parsed.get("title_en") or parsed.get("dataset_name") or parsed.get("job_title") or title
                            title_key = (item_title or "").strip().lower()[:60]
                            if title_key in all_extracted_titles:
                                cat_data["duplicates"] += 1
                                dup_label = "cross-query"
                            else:
                                all_extracted_titles.add(title_key)
                                dup_label = ""

                            extracted_count += 1
                            provider = llm.last_provider_used or "?"
                            cat_data["providers_used"].append(provider)
                            dup_str = f" [DUP]" if dup_label else ""
                            print(f"      [{idx+1}] ✓ conf={conf_score:.0f}% via {provider} ({llm_elapsed:.1f}s){dup_str}: {(item_title or '')[:50]}")
                        else:
                            cat_data["errors"].append(f"JSON parse fail: {url[:40]}")
                            print(f"      [{idx+1}] ✗ Unparseable JSON")
                    else:
                        cat_data["errors"].append(f"Empty LLM (groq_st={llm.last_status_code})")
                        print(f"      [{idx+1}] ✗ Empty response (st={llm.last_status_code})")
                except Exception as exc:
                    cat_data["errors"].append(f"{type(exc).__name__}: {str(exc)[:60]}")
                    print(f"      [{idx+1}] ✗ {type(exc).__name__}: {str(exc)[:60]}")

                await asyncio.sleep(2.0)  # Rate limit between LLM calls

            cat_data["validated"] += validated_count
            cat_data["extracted"] += extracted_count
            print(f"    → {validated_count} validated, {extracted_count} extracted")

            await asyncio.sleep(1.5)  # Between Tavily searches

    total_elapsed = time.time() - total_start

    # ─── ÉTAPE 5 — Final Report ──────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("  ÉTAPE 5 — Final Report")
    print("=" * 80)

    header = f"{'Category':<14}| {'Queries':>7} | {'Tavily':>6} | {'Results':>7} | {'Valid':>5} | {'Extrd':>5} | {'Conf%':>5} | {'Dups':>4} | {'Errs':>4}"
    sep = "-" * len(header)
    print(f"\n{header}")
    print(sep)

    totals = {"queries": 0, "tavily_ok": 0, "tavily_results": 0, "validated": 0,
              "extracted": 0, "conf_scores": [], "duplicates": 0, "errors": 0}

    for category in categories:
        d = results_by_category[category]
        avg_conf = sum(d["confidence_scores"]) / len(d["confidence_scores"]) if d["confidence_scores"] else 0
        print(f"{category:<14}| {d['queries']:>7} | {d['tavily_ok']:>6} | {d['tavily_results']:>7} | {d['validated']:>5} | {d['extracted']:>5} | {avg_conf:>4.0f}% | {d['duplicates']:>4} | {len(d['errors']):>4}")
        totals["queries"] += d["queries"]
        totals["tavily_ok"] += d["tavily_ok"]
        totals["tavily_results"] += d["tavily_results"]
        totals["validated"] += d["validated"]
        totals["extracted"] += d["extracted"]
        totals["conf_scores"].extend(d["confidence_scores"])
        totals["duplicates"] += d["duplicates"]
        totals["errors"] += len(d["errors"])

    avg = sum(totals["conf_scores"]) / len(totals["conf_scores"]) if totals["conf_scores"] else 0
    print(sep)
    print(f"{'TOTAL':<14}| {totals['queries']:>7} | {totals['tavily_ok']:>6} | {totals['tavily_results']:>7} | {totals['validated']:>5} | {totals['extracted']:>5} | {avg:>4.0f}% | {totals['duplicates']:>4} | {totals['errors']:>4}")
    print(f"\n  Duration: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")

    # Key rotation
    print(f"\n  API Key Rotation Status:")
    for prov in ["groq", "gemini", "tavily"]:
        idx = api_key_manager.get_current_index(prov)
        tot = len(api_key_manager.providers.get(prov, []))
        print(f"    {prov:>7}: index {idx}/{tot}")

    # Provider distribution
    all_providers = []
    for c in categories:
        all_providers.extend(results_by_category[c]["providers_used"])
    if all_providers:
        from collections import Counter
        pc = Counter(all_providers)
        print(f"\n  Provider Distribution: {dict(pc)}")

    # Error summary
    total_err_count = sum(len(results_by_category[c]["errors"]) for c in categories)
    if total_err_count:
        print(f"\n  Error Summary ({total_err_count} total):")
        for category in categories:
            errs = results_by_category[category]["errors"]
            if errs:
                unique = list(set(e[:80] for e in errs))
                print(f"    [{category}] {len(errs)} errors: {unique[0]}")

    # Analysis
    print(f"\n  ═══ Analysis ═══")
    if totals["tavily_ok"] == totals["queries"]:
        print(f"  ✓ Tavily: 100% success ({totals['tavily_ok']}/{totals['queries']})")
    else:
        print(f"  ⚠ Tavily: {totals['tavily_ok']}/{totals['queries']} succeeded")

    if totals["validated"] > 0:
        rate = totals["extracted"] / totals["validated"] * 100
        print(f"  • Extraction rate: {rate:.0f}% ({totals['extracted']}/{totals['validated']})")
    else:
        print(f"  ⚠ No items validated")

    if totals["duplicates"]:
        print(f"  • Cross-query duplicates: {totals['duplicates']}")

    if totals["conf_scores"]:
        print(f"  • Avg confidence: {avg:.1f}%")
        print(f"  • Min confidence: {min(totals['conf_scores']):.1f}%")
        print(f"  • Max confidence: {max(totals['conf_scores']):.1f}%")

    # Bottleneck
    if not gemini_ok and not groq_ok:
        print(f"  ⛔ BOTTLENECK: Both LLM providers are down")
    elif not groq_ok:
        print(f"  ⚠ BOTTLENECK: Groq rate-limited, using Gemini only")
    elif not gemini_ok:
        print(f"  ⚠ BOTTLENECK: Gemini down, using Groq only")

    # Save JSON
    output = {
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": round(total_elapsed, 1),
        "config": {
            "tavily_keys": len(tavily_keys), "groq_keys": len(groq_keys),
            "gemini_keys": len(gemini_keys), "groq_ok": groq_ok, "gemini_ok": gemini_ok,
        },
        "per_category": {c: {k: v for k, v in results_by_category[c].items()} for c in categories},
        "totals": totals,
    }
    output_path = os.path.join(os.path.dirname(__file__), "..", "reports", "e2e_scraping_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
